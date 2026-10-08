"""
Сервис для анализа тональности отзывов
"""

from typing import Dict, Any, List
from enum import Enum

from ..schemas.economics import ReviewStatus


class SentimentType(str, Enum):
    """Типы тональности"""
    VERY_POSITIVE = "very_positive"  # 5 звезд
    POSITIVE = "positive"            # 4 звезды
    NEUTRAL = "neutral"              # 3 звезды
    NEGATIVE = "negative"            # 2 звезды  
    VERY_NEGATIVE = "very_negative"  # 1 звезда


class SentimentService:
    """Сервис анализа тональности и определения приоритетов обработки отзывов"""
    
    def analyze_sentiment(self, rating: int, review_text: str = None) -> Dict[str, Any]:
        """
        Анализ тональности отзыва на основе рейтинга и текста
        """
        # Базовая тональность по рейтингу
        sentiment_map = {
            1: SentimentType.VERY_NEGATIVE,
            2: SentimentType.NEGATIVE, 
            3: SentimentType.NEUTRAL,
            4: SentimentType.POSITIVE,
            5: SentimentType.VERY_POSITIVE
        }
        
        base_sentiment = sentiment_map.get(rating, SentimentType.NEUTRAL)
        
        result = {
            "sentiment": base_sentiment,
            "confidence": self._calculate_confidence(rating, review_text),
            "priority": self._determine_priority(base_sentiment, review_text),
            "recommended_response_time": self._get_response_time_recommendation(base_sentiment),
            "keywords": []
        }
        
        # Анализ ключевых слов в тексте (если доступен)
        if review_text:
            result["keywords"] = self._extract_keywords(review_text)
            # Корректируем тональность на основе текста
            result["sentiment"] = self._adjust_sentiment_by_text(base_sentiment, review_text)
        
        return result
    
    def _calculate_confidence(self, rating: int, review_text: str = None) -> float:
        """Расчет уверенности в определении тональности"""
        
        base_confidence = 0.8  # Базовая уверенность по рейтингу
        
        if not review_text:
            return base_confidence
        
        text_length = len(review_text)
        
        # Длинные отзывы дают больше информации
        if text_length > 200:
            return min(0.95, base_confidence + 0.15)
        elif text_length > 50:
            return min(0.90, base_confidence + 0.10)
        else:
            return max(0.60, base_confidence - 0.20)
    
    def _determine_priority(self, sentiment: SentimentType, review_text: str = None) -> str:
        """Определение приоритета обработки отзыва"""
        
        priority_map = {
            SentimentType.VERY_NEGATIVE: "critical",    # Критический
            SentimentType.NEGATIVE: "high",             # Высокий
            SentimentType.NEUTRAL: "medium",            # Средний
            SentimentType.POSITIVE: "low",              # Низкий
            SentimentType.VERY_POSITIVE: "low"          # Низкий
        }
        
        base_priority = priority_map[sentiment]
        
        # Повышаем приоритет при наличии "тревожных" слов
        if review_text:
            critical_keywords = [
                "ужасно", "кошмар", "отвратительно", "никогда больше",
                "мошенники", "обман", "верну деньги", "жалобу подам",
                "суд", "прокуратура", "роспотребнадзор"
            ]
            
            if any(keyword in review_text.lower() for keyword in critical_keywords):
                if base_priority in ["high", "medium"]:
                    return "critical"
                elif base_priority == "low":
                    return "high"
        
        return base_priority
    
    def _get_response_time_recommendation(self, sentiment: SentimentType) -> Dict[str, Any]:
        """Рекомендации по времени ответа"""
        
        time_recommendations = {
            SentimentType.VERY_NEGATIVE: {
                "max_hours": 2,
                "ideal_hours": 0.5,
                "description": "Немедленно - в течение 30 минут"
            },
            SentimentType.NEGATIVE: {
                "max_hours": 6,
                "ideal_hours": 2,
                "description": "Срочно - в течение 2 часов"
            },
            SentimentType.NEUTRAL: {
                "max_hours": 24,
                "ideal_hours": 12,
                "description": "В течение рабочего дня"
            },
            SentimentType.POSITIVE: {
                "max_hours": 48,
                "ideal_hours": 24,
                "description": "В течение 1-2 дней"
            },
            SentimentType.VERY_POSITIVE: {
                "max_hours": 72,
                "ideal_hours": 48,
                "description": "В течение 2-3 дней"
            }
        }
        
        return time_recommendations[sentiment]
    
    def _extract_keywords(self, review_text: str) -> list[str]:
        """Извлечение ключевых слов из текста отзыва"""
        
        # Списки ключевых слов по категориям
        positive_keywords = [
            "отлично", "прекрасно", "замечательно", "супер", "великолепно",
            "рекомендую", "понравилось", "довольен", "спасибо", "качественно"
        ]
        
        negative_keywords = [
            "плохо", "ужасно", "отвратительно", "разочарован", "жалуюсь",
            "не рекомендую", "обман", "кошмар", "безобразие", "возмущен"
        ]
        
        problem_keywords = [
            "проблема", "ошибка", "не работает", "сломался", "дефект",
            "брак", "не соответствует", "задержка", "опоздание"
        ]
        
        service_keywords = [
            "персонал", "обслуживание", "сервис", "менеджер", "консультант",
            "доставка", "упаковка", "качество", "цена"
        ]
        
        found_keywords = []
        text_lower = review_text.lower()
        
        # Ищем совпадения в каждой категории
        for keyword in positive_keywords:
            if keyword in text_lower:
                found_keywords.append(f"positive:{keyword}")
        
        for keyword in negative_keywords:
            if keyword in text_lower:
                found_keywords.append(f"negative:{keyword}")
        
        for keyword in problem_keywords:
            if keyword in text_lower:
                found_keywords.append(f"problem:{keyword}")
        
        for keyword in service_keywords:
            if keyword in text_lower:
                found_keywords.append(f"service:{keyword}")
        
        return found_keywords
    
    def _adjust_sentiment_by_text(self, base_sentiment: SentimentType, review_text: str) -> SentimentType:
        """Корректировка тональности на основе текстового анализа"""
        
        text_lower = review_text.lower()
        
        # Сильные негативные маркеры могут понизить даже нейтральные отзывы
        very_negative_markers = ["ужасно", "кошмар", "отвратительно", "никогда больше"]
        if any(marker in text_lower for marker in very_negative_markers):
            if base_sentiment in [SentimentType.NEUTRAL, SentimentType.NEGATIVE]:
                return SentimentType.VERY_NEGATIVE
        
        # Сильные позитивные маркеры
        very_positive_markers = ["прекрасно", "великолепно", "идеально", "превосходно"]  
        if any(marker in text_lower for marker in very_positive_markers):
            if base_sentiment in [SentimentType.NEUTRAL, SentimentType.POSITIVE]:
                return SentimentType.VERY_POSITIVE
        
        # Иронические конструкции (сарказм) - понижают тональность
        sarcasm_markers = ["конечно же", "как же", "ну да", "естественно"]
        if any(marker in text_lower for marker in sarcasm_markers):
            sentiment_downgrade = {
                SentimentType.POSITIVE: SentimentType.NEUTRAL,
                SentimentType.VERY_POSITIVE: SentimentType.POSITIVE,
                SentimentType.NEUTRAL: SentimentType.NEGATIVE
            }
            return sentiment_downgrade.get(base_sentiment, base_sentiment)
        
        return base_sentiment
    
    def get_processing_recommendations(self, sentiment_data: Dict[str, Any]) -> list[str]:
        """Получить рекомендации по обработке отзыва"""
        
        recommendations = []
        sentiment = sentiment_data["sentiment"] 
        priority = sentiment_data["priority"]
        
        if priority == "critical":
            recommendations.extend([
                "🚨 КРИТИЧЕСКИЙ ПРИОРИТЕТ",
                "🤖 Немедленно активировать SI-ядро для генерации ответа",
                "📞 Рассмотреть персональный контакт с клиентом",
                "🎁 Подготовить компенсационное предложение"
            ])
        
        elif priority == "high":
            recommendations.extend([
                "⚠️ Высокий приоритет обработки",
                "🤖 Запустить генерацию ответа в течение 2 часов",
                "📊 Мониторить влияние на конверсию"
            ])
        
        elif sentiment in [SentimentType.POSITIVE, SentimentType.VERY_POSITIVE]:
            recommendations.extend([
                "✅ Позитивный отзыв - поддержать клиента", 
                "📈 Использовать для маркетинговых материалов",
                "💝 Поблагодарить клиента за лояльность"
            ])
        
        else:
            recommendations.append("📝 Стандартная обработка в плановом режиме")
        
        return recommendations