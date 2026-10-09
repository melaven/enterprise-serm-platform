"""
Сервис для работы с LLM (Language Model) - генерация ответов на отзывы через Google Gemini API
Заменил OpenAI на Gemini 1.5 Flash для генерации ответов
"""

import logging
from typing import Optional, Dict, Any
import google.generativeai as genai
from config import get_settings

from ..exceptions import LLMServiceError

logger = logging.getLogger(__name__)


class LLMService:
    """Сервис для генерации ответов на отзывы через Google Gemini API"""
    
    def __init__(self):
        settings = get_settings()
        if not settings.gemini_api_key:
            raise LLMServiceError("Не настроен GEMINI_API_KEY")
        
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        self.generation_config = {
            "temperature": 0.7,  # Баланс между креативностью и консистентностью
            "top_p": 0.8,
            "top_k": 20,
            "max_output_tokens": 400,
        }
        logger.info(f"✅ Gemini LLM сервис инициализирован с моделью {settings.gemini_model}")
    
    async def generate_review_response(self,
                                     review_text: str,
                                     rating: int,
                                     author_name: str = None,
                                     company_name: str = None,
                                     custom_context: Dict[str, Any] = None) -> str:
        """
        Генерация профессионального ответа на отзыв через Gemini API
        """
        try:
            logger.info("🤖 Генерация ответа на отзыв через Gemini...")
            
            # Формируем единый промпт для Gemini
            prompt = self._build_prompt(review_text, rating, author_name, company_name, custom_context)
            
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            
            generated_response = response.text.strip()
            
            # Проверяем качество ответа
            if len(generated_response.strip()) < 10:
                raise LLMServiceError("Сгенерированный ответ слишком короткий")
            
            logger.info("✅ Ответ успешно сгенерирован через Gemini")
            return generated_response
        
        except Exception as e:
            if isinstance(e, LLMServiceError):
                raise
            logger.error(f"❌ Ошибка Gemini API: {e}")
            raise LLMServiceError(f"Ошибка генерации ответа: {str(e)}")
    
    def _build_prompt(self, review_text: str, rating: int, author_name: str = None, 
                     company_name: str = None, custom_context: Dict[str, Any] = None) -> str:
        """Построение промпта для Gemini"""
        
        company_info = f"от имени компании {company_name}" if company_name else "от имени компании"
        author_info = f"клиенту {author_name}" if author_name else "клиенту"
        
        prompt = f"""
Ты - профессиональный менеджер по работе с клиентами российской компании. 
Напиши вежливый, профессиональный и полезный ответ на отзыв {author_info} {company_info} на русском языке.

ПРИНЦИПЫ ОТВЕТОВ:
- Всегда благодари за обратную связь
- Будь искренним и человечным
- Для негативных отзывов (1-2 звезды): извинись и предложи конкретное решение
- Для нейтральных отзывов (3 звезды): поблагодари и предложи улучшения
- Для позитивных отзывов (4-5 звезд): поблагодари и поддержи позитив
- Избегай шаблонных фраз
- Длина ответа: 2-4 предложения
- Тон: дружелюбный, профессиональный, искренний

ДАННЫЕ ОТЗЫВА:
Рейтинг: {rating}/5
Текст отзыва: "{review_text}"
"""

        if author_name:
            prompt += f"Имя автора: {author_name}\n"

        if custom_context:
            if custom_context.get("response_style"):
                prompt += f"Стиль ответов: {custom_context['response_style']}\n"
            if custom_context.get("special_offers"):
                prompt += f"Можешь предложить: {custom_context['special_offers']}\n"

        prompt += "\nНапиши профессиональный ответ на этот отзыв:"
        
        return prompt
    
    async def generate_bulk_responses(self,
                                    reviews_data: list[Dict[str, Any]],
                                    company_name: str = None) -> list[Dict[str, Any]]:
        """
        Массовая генерация ответов для нескольких отзывов
        """
        logger.info(f"🔄 Массовая генерация ответов для {len(reviews_data)} отзывов")
        results = []
        
        for review_data in reviews_data:
            try:
                response = await self.generate_review_response(
                    review_text=review_data["text"],
                    rating=review_data["rating"],
                    author_name=review_data.get("author_name"),
                    company_name=company_name
                )
                
                results.append({
                    "review_id": review_data.get("id"),
                    "generated_response": response,
                    "success": True
                })
            
            except Exception as e:
                logger.error(f"❌ Ошибка генерации для отзыва {review_data.get('id')}: {e}")
                results.append({
                    "review_id": review_data.get("id"),
                    "generated_response": None,
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    async def generate_follow_up_message(self,
                                       original_review: str,
                                       company_response: str,
                                       client_reply: str = None) -> str:
        """
        Генерация дополнительного сообщения для продолжения диалога
        """
        try:
            logger.info("📞 Генерация follow-up сообщения через Gemini")
            
            prompt = f"""
Ты помогаешь продолжить диалог с клиентом после первоначального ответа компании.
Напиши дружелюбное follow-up сообщение на русском языке, которое:
- Подтверждает заботу о клиенте
- При необходимости уточняет детали решения проблемы
- Поддерживает позитивные отношения
- Длина: 1-2 предложения

КОНТЕКСТ ДИАЛОГА:
Изначальный отзыв клиента: "{original_review}"
Ответ компании: "{company_response}"
"""
            
            if client_reply:
                prompt += f'Ответ клиента: "{client_reply}"\n'
            
            prompt += "\nНапиши подходящее follow-up сообщение:"
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    **self.generation_config,
                    "max_output_tokens": 200
                }
            )
            
            return response.text.strip()
        
        except Exception as e:
            logger.error(f"❌ Ошибка генерации follow-up: {e}")
            raise LLMServiceError(f"Ошибка генерации follow-up сообщения: {str(e)}")
    
    def validate_api_connection(self) -> bool:
        """Проверка доступности Gemini API"""
        try:
            settings = get_settings()
            return bool(settings.gemini_api_key and settings.gemini_api_key != "dummy_key_for_testing")
        except Exception:
            return False