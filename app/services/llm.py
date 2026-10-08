"""
Сервис для работы с LLM (Language Model) - генерация ответов на отзывы
"""

import os
from typing import Optional, Dict, Any

from openai import AsyncOpenAI

from ..exceptions import LLMServiceError


class LLMService:
    """Сервис для генерации ответов на отзывы через OpenAI API"""
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMServiceError("Не настроен OPENAI_API_KEY")
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    async def generate_review_response(self,
                                     review_text: str,
                                     rating: int,
                                     author_name: str = None,
                                     company_name: str = None,
                                     custom_context: Dict[str, Any] = None) -> str:
        """
        Генерация профессионального ответа на отзыв
        """
        try:
            # Формируем контекст для генерации
            system_prompt = self._build_system_prompt(company_name, custom_context)
            user_prompt = self._build_user_prompt(review_text, rating, author_name)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=300,
                temperature=0.7,  # Баланс между креативностью и консистентностью
                presence_penalty=0.1,  # Избегаем повторов
                frequency_penalty=0.1
            )
            
            generated_response = response.choices[0].message.content or ""
            
            # Проверяем качество ответа
            if len(generated_response.strip()) < 10:
                raise LLMServiceError("Сгенерированный ответ слишком короткий")
            
            return generated_response.strip()
        
        except Exception as e:
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Ошибка генерации ответа: {str(e)}")
    
    def _build_system_prompt(self, company_name: str = None, custom_context: Dict[str, Any] = None) -> str:
        """Построение системного промпта"""
        
        base_prompt = """Ты - профессиональный менеджер по работе с клиентами российской компании. 
Твоя задача - написать вежливый, профессиональный и полезный ответ на отзыв клиента на русском языке.

ПРИНЦИПЫ ОТВЕТОВ:
- Всегда благодари за обратную связь
- Будь искренним и человечным
- Для негативных отзывов: извинись и предложи решение
- Для позитивных отзывов: поблагодари и поддержи позитив
- Избегай шаблонных фраз
- Длина ответа: 2-4 предложения
- Тон: дружелюбный, профессиональный"""
        
        if company_name:
            base_prompt += f"\n\nТы представляешь компанию: {company_name}"
        
        if custom_context:
            if custom_context.get("response_style"):
                base_prompt += f"\n\nСтиль ответов: {custom_context['response_style']}"
            
            if custom_context.get("special_offers"):
                base_prompt += f"\n\nМожешь предложить: {custom_context['special_offers']}"
        
        return base_prompt
    
    def _build_user_prompt(self, review_text: str, rating: int, author_name: str = None) -> str:
        """Построение пользовательского промпта"""
        
        prompt = f"Рейтинг: {rating}/5\nТекст отзыва: {review_text}"
        
        if author_name:
            prompt += f"\nИмя автора: {author_name}"
        
        return prompt
    
    async def generate_bulk_responses(self,
                                    reviews_data: list[Dict[str, Any]],
                                    company_name: str = None) -> list[Dict[str, Any]]:
        """
        Массовая генерация ответов для нескольких отзывов
        """
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
            system_prompt = """Ты помогаешь продолжить диалог с клиентом после первоначального ответа компании.
Твоя задача - написать дружелюбное follow-up сообщение, которое:
- Подтверждает заботу о клиенте
- При необходимости уточняет детали решения проблемы
- Поддерживает позитивные отношения
- Длина: 1-2 предложения"""
            
            user_prompt = f"""Изначальный отзыв клиента: {original_review}
Ответ компании: {company_response}"""
            
            if client_reply:
                user_prompt += f"\nОтвет клиента: {client_reply}"
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=150,
                temperature=0.6
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            raise LLMServiceError(f"Ошибка генерации follow-up сообщения: {str(e)}")
    
    def validate_api_connection(self) -> bool:
        """Проверка доступности OpenAI API"""
        try:
            # Простая проверка подключения (без лишних запросов)
            return bool(self.client.api_key)
        except Exception:
            return False