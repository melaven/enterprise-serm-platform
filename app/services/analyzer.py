"""
Анализатор тональности отзывов с Google Gemini API
Заменил OpenAI на Gemini 1.5 Flash для анализа отзывов
"""

import logging
import json
from typing import List
import google.generativeai as genai
from config import get_settings

from app.schemas.analytics import ReviewAnalytics

logger = logging.getLogger(__name__)


class ReviewAnalyzerService:
    """Сервис анализа отзывов с Google Gemini API"""
    
    def __init__(self):
        """Инициализация Gemini клиента"""
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        self.generation_config = {
            "temperature": 0.1,  # Низкая температура для стабильного анализа
            "top_p": 0.8,
            "top_k": 20,
            "max_output_tokens": 1000,
        }
        logger.info(f"✅ Gemini API инициализирован с моделью {settings.gemini_model}")

    async def analyze_review(self, text: str, rating: int) -> ReviewAnalytics:
        """
        Анализирует текст и оценку, возвращает тональность и теги с помощью Gemini API.
        
        Args:
            text: Текст отзыва
            rating: Оценка от 1 до 5
            
        Returns:
            ReviewAnalytics: Результат анализа с тональностью и тегами
        """
        logger.info("🔍 Запуск анализа отзыва через Gemini API...")
        
        try:
            prompt = f"""
Проанализируй следующий отзыв и верни результат в JSON формате.

Текст отзыва: "{text}"
Оценка: {rating}/5

Определи:
1. Тональность (sentiment): "Positive", "Neutral", или "Negative"
2. Ключевые теги (tags): массив от 2 до 5 тегов на русском языке, описывающих основные аспекты отзыва

Верни результат строго в следующем JSON формате:
{{
    "sentiment": "Positive|Neutral|Negative",
    "tags": ["тег1", "тег2", "тег3"]
}}

Учитывай и текст, и числовую оценку. Теги должны отражать конкретные аспекты: сервис, цена, качество, время ожидания, персонал, еда, атмосфера и т.д.
"""

            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            
            # Извлекаем JSON из ответа
            response_text = response.text.strip()
            
            # Убираем возможные markdown блоки
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            try:
                result = json.loads(response_text)
                
                # Валидация результата
                sentiment = result.get("sentiment", "Neutral")
                if sentiment not in ["Positive", "Neutral", "Negative"]:
                    sentiment = "Neutral"
                
                tags = result.get("tags", [])
                if not isinstance(tags, list) or len(tags) == 0:
                    tags = ["общий"]
                
                logger.info(f"✅ Gemini анализ завершен: {sentiment}, теги: {tags}")
                
                return ReviewAnalytics(
                    sentiment=sentiment,
                    tags=tags[:5]  # Максимум 5 тегов
                )
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Ошибка парсинга JSON от Gemini: {e}")
                logger.error(f"Ответ Gemini: {response_text}")
                return self._fallback_analysis(rating)
                
        except Exception as e:
            logger.error(f"❌ Ошибка при вызове Gemini API: {e}")
            return self._fallback_analysis(rating)
    
    def _fallback_analysis(self, rating: int) -> ReviewAnalytics:
        """Резервный анализ на основе рейтинга при ошибке API"""
        logger.warning("🔄 Используем резервный анализ на основе рейтинга")
        
        if rating >= 4:
            return ReviewAnalytics(
                sentiment="Positive", 
                tags=["качество", "довольный_клиент"]
            )
        elif rating == 3:
            return ReviewAnalytics(
                sentiment="Neutral", 
                tags=["стандартно", "без_эмоций"]
            )
        else:
            return ReviewAnalytics(
                sentiment="Negative", 
                tags=["жалоба", "проблема_сервиса"]
            )
    
    async def extract_tags(self, text: str) -> List[str]:
        """
        Извлекает ключевые теги из текста отзыва с помощью Gemini
        
        Args:
            text: Текст отзыва
            
        Returns:
            List[str]: Список тегов
        """
        logger.info("🏷️ Извлечение тегов из текста через Gemini API...")
        
        try:
            prompt = f"""
Извлеки ключевые теги из следующего текста отзыва на русском языке.

Текст: "{text}"

Верни 3-5 конкретных тегов, которые отражают основные аспекты, упомянутые в отзыве.
Примеры хороших тегов: "сервис", "цена", "качество", "персонал", "атмосфера", "еда", "время_ожидания", "чистота", "расположение".

Верни результат в JSON формате:
{{
    "tags": ["тег1", "тег2", "тег3"]
}}
"""

            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            
            response_text = response.text.strip()
            
            # Убираем markdown блоки
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            try:
                result = json.loads(response_text)
                tags = result.get("tags", [])
                
                if isinstance(tags, list) and len(tags) > 0:
                    logger.info(f"✅ Теги извлечены: {tags}")
                    return tags[:5]  # Максимум 5 тегов
                else:
                    return ["общий"]
                    
            except json.JSONDecodeError:
                logger.error(f"❌ Ошибка парсинга JSON для тегов: {response_text}")
                return ["общий"]
                
        except Exception as e:
            logger.error(f"❌ Ошибка при извлечении тегов через Gemini: {e}")
            return ["общий"]