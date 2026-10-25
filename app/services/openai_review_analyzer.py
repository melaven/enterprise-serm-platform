"""
OpenAI-based Review Analyzer with Structured Outputs
Production-grade async LLM integration for SERM
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog
from openai import AsyncOpenAI
from openai import AsyncOpenAI as AsyncClient
from pydantic import BaseModel, Field, field_validator

from ..core.config import get_settings
from ..core.exceptions import LLMServiceError

logger = structlog.get_logger(__name__)

# Configuration
DEFAULT_MODEL = "gpt-4o-mini"  # Cost-effective for production
DEFAULT_TIMEOUT = 30.0  # seconds
MAX_RETRIES = 3
MAX_REVIEW_CHARS = 4000
MAX_TAGS = 10
MAX_REPLY_CHARS = 500


# ============================================================================
# Enums & Schemas
# ============================================================================


class Sentiment(str, Enum):
    """Sentiment classification"""
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class ReviewAnalysisSchema(BaseModel):
    """
    Structured output schema for OpenAI response_format
    Strict validation for reliable LLM responses
    """
    
    sentiment: Sentiment = Field(
        description="Overall sentiment: POSITIVE, NEUTRAL, or NEGATIVE"
    )
    
    threat_level: int = Field(
        ge=0,
        le=10,
        description="Threat level from 0 (no threat) to 10 (critical legal/safety threat)"
    )
    
    tags: list[str] = Field(
        default_factory=list,
        max_length=MAX_TAGS,
        description="Key tags extracted from review (e.g., 'service', 'quality', 'delivery')"
    )
    
    suggested_reply: str = Field(
        min_length=50,
        max_length=MAX_REPLY_CHARS,
        description="Professional B2B response draft in review's language"
    )
    
    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        """Clean and deduplicate tags"""
        seen = set()
        cleaned = []
        for tag in value:
            normalized = tag.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                cleaned.append(tag.strip())
        return cleaned[:MAX_TAGS]
    
    @field_validator("suggested_reply")
    @classmethod
    def validate_reply(cls, value: str) -> str:
        """Ensure reply is professional and safe"""
        reply = value.strip()
        
        # Basic content validation
        forbidden = ["http", "www.", "@", "+", "refund", "compensation", "sorry"]
        for word in forbidden:
            if word.lower() in reply.lower():
                raise ValueError(f"Reply contains forbidden content: {word}")
        
        return reply


# ============================================================================
# Analysis Result
# ============================================================================


@dataclass
class AnalysisResult:
    """Complete analysis result with metadata"""
    
    sentiment: str
    threat_level: int
    tags: list[str]
    suggested_reply: str
    is_fallback: bool = False
    tokens_used: int = 0
    model_used: str = DEFAULT_MODEL


# ============================================================================
# OpenAI LLM Service
# ============================================================================


class OpenAIReviewAnalyzer:
    """
    Production OpenAI analyzer with structured outputs
    
    Features:
    - Async OpenAI client
    - Structured outputs via response_format
    - Timeout handling
    - Retry logic with exponential backoff
    - Fallback on failures
    """
    
    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        settings = get_settings()
        self.api_key = api_key or getattr(settings, "openai_api_key", None)
        
        if not self.api_key:
            raise LLMServiceError("OPENAI_API_KEY not configured")
        
        self.model = model
        self.timeout = timeout
        self.client = AsyncClient(api_key=self.api_key)
        
        logger.info(
            "openai_analyzer_initialized",
            model=self.model,
            timeout=self.timeout,
        )
    
    async def analyze_review(
        self,
        review_text: str,
        *,
        rating: int | None = None,
        platform: str | None = None,
    ) -> AnalysisResult:
        """
        Analyze review with OpenAI structured outputs
        
        Args:
            review_text: Review text to analyze
            rating: Review rating (1-5) for context
            platform: Platform name for context
            
        Returns:
            AnalysisResult with sentiment, threat_level, tags, suggested_reply
            
        Raises:
            LLMServiceError: On unrecoverable failures
        """
        if not review_text.strip():
            raise LLMServiceError("Review text is empty")
        
        # Truncate review if too long
        review_text = review_text[:MAX_REVIEW_CHARS].strip()
        
        # Build prompt with context
        prompt = self._build_prompt(review_text, rating, platform)
        
        try:
            result = await self._analyze_with_retry(prompt)
            logger.info(
                "openai_analysis_completed",
                sentiment=result.sentiment,
                threat_level=result.threat_level,
                tags_count=len(result.tags),
                is_fallback=result.is_fallback,
            )
            return result
            
        except Exception as exc:
            logger.error("openai_analysis_failed", error=str(exc), exc_info=True)
            # Return fallback on any error
            return self._fallback_analysis(review_text, rating)
    
    def _build_prompt(
        self, review_text: str, rating: int | None, platform: str | None
    ) -> str:
        """Build user prompt with context"""
        lines = []
        
        if platform:
            lines.append(f"Platform: {platform}")
        if rating is not None:
            lines.append(f"Rating: {rating}/5")
        
        lines.append("Review:")
        lines.append(review_text)
        lines.append("")
        lines.append("Analyze this review and return JSON matching the schema.")
        
        return "\n".join(lines)
    
    async def _analyze_with_retry(self, prompt: str) -> AnalysisResult:
        """
        Execute analysis with retry logic
        
        Retry on:
        - Rate limit errors (429)
        - Server errors (5xx)
        - Timeout errors
        """
        system_prompt = """You are a professional reputation management analyst for a B2B platform.
Analyze customer reviews and return structured JSON.

Rules:
- sentiment: POSITIVE (satisfied), NEUTRAL (mixed), NEGATIVE (dissatisfied)
- threat_level: 0-10 scale. 0=no threat, 5=requires attention, 10=critical (legal/safety threats)
- tags: Extract 3-5 key topics (e.g., "service", "quality", "delivery", "staff")
- suggested_reply: Professional B2B response in review's language. Thank, acknowledge, offer help. NO apologies, NO promises, NO liability admission.
- Length: 50-500 characters for reply"""

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": "review_analysis",
                                "strict": True,
                                "schema": ReviewAnalysisSchema.model_json_schema(),
                            },
                        },
                        temperature=0.0,  # Deterministic for structured outputs
                        max_tokens=500,
                    ),
                    timeout=self.timeout,
                )
                
                # Parse response
                content = response.choices[0].message.content
                if not content:
                    raise LLMServiceError("Empty response from OpenAI")
                
                # Validate with Pydantic
                schema = ReviewAnalysisSchema.model_validate_json(content)
                
                return AnalysisResult(
                    sentiment=schema.sentiment.value,
                    threat_level=schema.threat_level,
                    tags=schema.tags,
                    suggested_reply=schema.suggested_reply,
                    is_fallback=False,
                    tokens_used=response.usage.total_tokens if response.usage else 0,
                    model_used=self.model,
                )
                
            except asyncio.TimeoutError:
                logger.warning(
                    "openai_timeout",
                    attempt=attempt,
                    max_attempts=MAX_RETRIES,
                )
                if attempt == MAX_RETRIES:
                    raise LLMServiceError("OpenAI request timed out")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as exc:
                logger.warning(
                    "openai_request_failed",
                    attempt=attempt,
                    max_attempts=MAX_RETRIES,
                    error=str(exc),
                )
                if attempt == MAX_RETRIES:
                    raise LLMServiceError(f"OpenAI request failed: {exc}")
                await asyncio.sleep(2 ** attempt)
        
        # Should not reach here
        raise LLMServiceError("Unexpected retry loop exit")
    
    def _fallback_analysis(
        self, review_text: str, rating: int | None
    ) -> AnalysisResult:
        """
        Rule-based fallback when LLM fails
        
        Guarantees system always returns valid result
        """
        logger.warning("using_fallback_analysis", review_length=len(review_text))
        
        # Rule-based sentiment
        if rating is None:
            sentiment = Sentiment.NEUTRAL
        elif rating >= 4:
            sentiment = Sentiment.POSITIVE
        elif rating <= 2:
            sentiment = Sentiment.NEGATIVE
        else:
            sentiment = Sentiment.NEUTRAL
        
        # Rule-based threat level
        if rating is not None and rating <= 1:
            threat_level = 7
        elif rating is not None and rating <= 2:
            threat_level = 4
        else:
            threat_level = 0
        
        # Language detection for reply
        cyrillic_chars = sum(1 for c in review_text if "\u0400" <= c <= "\u04ff")
        is_russian = (cyrillic_chars / max(len(review_text), 1)) > 0.3
        
        if is_russian:
            reply = "Благодарим за ваш отзыв. Мы внимательно изучим ситуацию и свяжемся с вами для решения вопроса."
        else:
            reply = "Thank you for your feedback. We take your concerns seriously and will investigate this matter."
        
        return AnalysisResult(
            sentiment=sentiment.value,
            threat_level=threat_level,
            tags=["review"],
            suggested_reply=reply,
            is_fallback=True,
            tokens_used=0,
            model_used="rule_based_fallback",
        )
    
    async def close(self):
        """Close the OpenAI client"""
        await self.client.close()


# ============================================================================
# Factory
# ============================================================================


def create_openai_analyzer(
    api_key: str | None = None, **kwargs
) -> OpenAIReviewAnalyzer:
    """Factory function for creating OpenAI analyzer"""
    return OpenAIReviewAnalyzer(api_key=api_key, **kwargs)
