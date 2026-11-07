"""
LLM Reply Generator — Production-ready AI-powered reply generation

This service generates automatic replies to customer reviews using LLM APIs
(OpenRouter/Claude/OpenAI/Groq) with proper error handling and retry logic.

Features:
- Async HTTP client (httpx/OpenAI SDK)
- Tone-of-Voice prompts for B2B responses
- Rate limit handling (HTTP 429)
- Exponential backoff via tenacity
- Provider flexibility via environment variables

Usage:
    generator = LLMReplyGenerator()
    reply = await generator.generate_reply(
        text="Отличный сервис!",
        rating=5
    )
"""

import os
from typing import Literal

from openai import AsyncOpenAI as AsyncClient
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.exceptions import LLMServiceError
from app.core.logger import get_logger

logger = get_logger(__name__)

# Configuration
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3


class LLMReplyGenerator:
    """
    LLM-powered reply generator for customer reviews.

    Generates polite, professional B2B responses based on:
    - Review text content
    - Rating (positive/negative tone adjustment)
    - Company tone-of-voice policy
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """
        Initialize the LLM client.

        Args:
            api_key: LLM API key (defaults to env var)
            model: Model name (defaults to DEFAULT_MODEL)
            base_url: API base URL (for custom providers)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL)
        self.base_url = base_url or os.getenv("LLM_BASE_URL")

        if not self.api_key:
            raise ValueError("LLM_API_KEY or OPENAI_API_KEY must be configured")

        self.client = AsyncClient(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=DEFAULT_TIMEOUT,
        )

    def _build_system_prompt(self, rating: int) -> str:
        """
        Build system prompt based on review rating.

        Args:
            rating: Review rating (1-5)

        Returns:
            System prompt string
        """
        if rating >= 4:
            return """You are a polite B2B customer service representative. 
Generate a brief, professional thank-you message for a positive review.
- Thank the customer
- Express appreciation for their feedback
- Mention you value their business
- Keep it under 200 characters
- Do not be overly enthusiastic or use emojis
- Professional and concise tone"""
        elif rating == 3:
            return """You are a polite B2B customer service representative.
Generate a brief, professional response for a neutral review.
- Thank the customer for feedback
- Express commitment to improvement
- Invite them to contact support if needed
- Keep it under 200 characters
- Professional and balanced tone"""
        else:
            return """You are a polite B2B customer service representative.
Generate a brief, professional apology for a negative review.
- Acknowledge the issue
- Express sincere apology
- Offer to resolve the problem
- Provide contact information for support
- Keep it under 300 characters
- Empathetic but professional tone
- Do not make excuses or be defensive"""

    def _log_retry_attempt(self, retry_state: RetryCallState) -> None:
        """Log retry attempts for monitoring."""
        logger.warning(
            "llm_reply_generation_retry",
            attempt=retry_state.attempt_number,
            max_attempts=MAX_RETRIES,
            exception=str(retry_state.outcome.exception()) if retry_state.outcome else None,
        )

    def _is_retryable_error(self, exception: Exception) -> bool:
        """Determine if exception is retryable (429, 5xx, timeout)."""
        if hasattr(exception, "status_code"):
            status_code = exception.status_code
            return status_code in (429, 500, 502, 503, 504)

        error_str = str(exception).lower()
        return any(
            keyword in error_str
            for keyword in ("timeout", "connection", "429", "500", "502", "503", "504")
        )

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=_log_retry_attempt,
        reraise=True,
    )
    async def generate_reply(self, text: str, rating: int) -> str:
        """
        Generate an AI-powered reply to a review.

        Args:
            text: Review text (sanitized)
            rating: Review rating (1-5)

        Returns:
            Generated reply text

        Raises:
            LLMServiceError: If generation fails after retries
        """
        if not text or not text.strip():
            raise ValueError("Review text cannot be empty")

        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        system_prompt = self._build_system_prompt(rating)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Review: {text}"},
                ],
                temperature=0.7,
                max_tokens=150,
            )

            reply = response.choices[0].message.content or ""
            logger.info(
                "llm_reply_generated",
                model=self.model,
                rating=rating,
                reply_length=len(reply),
            )
            return reply

        except Exception as exc:
            error_msg = str(exc)
            logger.error(
                "llm_reply_generation_failed",
                error=error_msg,
                model=self.model,
                rating=rating,
                exc_info=True,
            )

            # Re-raise for ARQ retry logic
            raise LLMServiceError(f"Failed to generate reply: {error_msg}") from exc

    async def close(self) -> None:
        """Close the async client."""
        await self.client.close()


# ============================================================================
# Convenience Functions
# ============================================================================


async def generate_review_reply(text: str, rating: int) -> str:
    """
    Convenience function to generate a review reply.

    Example:
        reply = await generate_review_reply("Great service!", 5)
    """
    generator = LLMReplyGenerator()
    try:
        return await generator.generate_reply(text, rating)
    finally:
        await generator.close()
