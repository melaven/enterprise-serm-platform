"""
Сервис для работы с LLM (Language Model) - анализ отзывов через Google Gemini API
Обновлен до нового google-genai SDK с детерминированным анализом
"""

from typing import Any

from ..core.config import get_settings
from ..core.exceptions import LLMServiceError
from ..core.logger import get_logger
from .llm_analyzer import (
    AnalysisOutcome,
    LLMAnalysisError,
    LLMTransportError,
    build_gemini_analyzer,
)

logger = get_logger(__name__)


class LLMService:
    """Сервис для анализа отзывов через Google Gemini API (новый google-genai SDK)"""

    def __init__(self):
        settings = get_settings()
        if not settings.gemini_api_key:
            raise LLMServiceError("Не настроен GEMINI_API_KEY")

        try:
            self.analyzer = build_gemini_analyzer(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                timeout_s=30.0,
            )
            logger.info(
                "LLM service initialized",
                model=settings.gemini_model,
                sdk="google-genai",
            )
        except Exception as e:
            logger.error("LLM service initialization failed", error=str(e))
            raise LLMServiceError(f"Ошибка инициализации LLM: {e}")

    async def analyze_review(
        self, review_text: str, rating: int | None = None, platform: str | None = None
    ) -> dict[str, Any]:
        """
        Анализ отзыва с использованием детерминированного LLM-анализатора

        Args:
            review_text: Текст отзыва
            rating: Рейтинг (1-5)
            platform: Название платформы

        Returns:
            Результат анализа в формате словаря

        Raises:
            LLMServiceError: При ошибках анализа
        """
        try:
            logger.info(
                "Review analysis started",
                review_chars=len(review_text),
                rating=rating,
                platform=platform,
            )

            result = await self.analyzer.analyze(
                review_text, rating=rating, platform=platform
            )

            analysis_dict = {
                "sentiment": result.sentiment.value,
                "issue_category": result.issue_category.value,
                "extracted_entities": result.extracted_entities,
                "is_critical": result.is_critical,
                "suggested_reply": result.suggested_reply,
            }

            logger.info(
                "Review analysis completed",
                sentiment=result.sentiment.value,
                is_critical=result.is_critical,
                entities_count=len(result.extracted_entities),
            )

            return analysis_dict

        except LLMTransportError as e:
            # Транспортные ошибки пробрасываем для retry в ARQ
            logger.warning("LLM transport error", error=str(e))
            raise
        except LLMAnalysisError as e:
            logger.error(
                "LLM analysis error", error=str(e), error_type=type(e).__name__
            )
            raise LLMServiceError(f"Ошибка анализа отзыва: {e}")
        except Exception as e:
            logger.error("Unexpected LLM error", error=str(e))
            raise LLMServiceError(f"Неожиданная ошибка LLM: {e}")

    async def analyze_review_safe(
        self, review_text: str, rating: int | None = None, platform: str | None = None
    ) -> dict[str, Any]:
        """
        Безопасный анализ отзыва с fallback

        Всегда возвращает результат, даже при ошибках LLM
        """
        try:
            outcome: AnalysisOutcome = await self.analyzer.analyze_safe(
                review_text, rating=rating, platform=platform
            )

            analysis_dict = {
                "sentiment": outcome.result.sentiment.value,
                "issue_category": outcome.result.issue_category.value,
                "extracted_entities": outcome.result.extracted_entities,
                "is_critical": outcome.result.is_critical,
                "suggested_reply": outcome.result.suggested_reply,
                "is_fallback": outcome.is_fallback,
            }

            if outcome.is_fallback:
                logger.warning(
                    "Used fallback analysis", rating=rating, platform=platform
                )

            return analysis_dict

        except Exception as e:
            logger.error("Safe analysis failed completely", error=str(e))
            # Крайний fallback - если и safe метод упал
            return {
                "sentiment": "NEUTRAL",
                "issue_category": "OTHER",
                "extracted_entities": [],
                "is_critical": rating is not None and rating <= 2,
                "suggested_reply": "Спасибо за ваш отзыв! Мы внимательно изучим ситуацию.",
                "is_fallback": True,
            }

    # Методы для обратной совместимости со старым API
    async def generate_review_response(
        self,
        review_text: str,
        rating: int,
        author_name: str = None,
        company_name: str = None,
        custom_context: dict[str, Any] = None,
    ) -> str:
        """
        Генерация ответа на отзыв (обратная совместимость)

        Использует новый анализатор для генерации suggested_reply
        """
        try:
            analysis = await self.analyze_review_safe(review_text, rating=rating)
            return analysis["suggested_reply"]
        except Exception as e:
            logger.error("Review response generation failed", error=str(e))
            raise LLMServiceError(f"Ошибка генерации ответа: {e}")

    async def generate_bulk_responses(
        self, reviews_data: list[dict[str, Any]], company_name: str = None
    ) -> list[dict[str, Any]]:
        """
        Массовая генерация ответов (обратная совместимость)
        """
        logger.info("Bulk analysis started", reviews_count=len(reviews_data))
        results = []

        for review_data in reviews_data:
            try:
                analysis = await self.analyze_review_safe(
                    review_text=review_data["text"], rating=review_data.get("rating")
                )

                results.append(
                    {
                        "review_id": review_data.get("id"),
                        "generated_response": analysis["suggested_reply"],
                        "analysis": analysis,
                        "success": True,
                    }
                )

            except Exception as e:
                logger.error(
                    "Bulk analysis item failed",
                    review_id=review_data.get("id"),
                    error=str(e),
                )
                results.append(
                    {
                        "review_id": review_data.get("id"),
                        "generated_response": None,
                        "analysis": None,
                        "success": False,
                        "error": str(e),
                    }
                )

        logger.info(
            "Bulk analysis completed",
            total=len(results),
            successful=sum(1 for r in results if r["success"]),
        )
        return results

    def validate_api_connection(self) -> bool:
        """Проверка доступности Gemini API"""
        try:
            settings = get_settings()
            return bool(
                settings.gemini_api_key
                and settings.gemini_api_key != "dummy_key_for_testing"
            )
        except Exception:
            return False
