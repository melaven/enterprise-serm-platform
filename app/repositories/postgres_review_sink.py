"""
PostgresReviewSink - реализация сохранения отзывов в PostgreSQL.
Использует bulk insert с ON CONFLICT DO NOTHING для идемпотентности.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.economics import Review, Platform

if TYPE_CHECKING:
    from app.services.ai_processor import EnrichedReview


class PostgresReviewSink:
    """
    Sink для массовой записи спарсенных отзывов в PostgreSQL.
    
    Особенности:
    - Bulk insert для производительности
    - ON CONFLICT DO NOTHING по (company_id, platform, external_review_id)
    - Автоматическое создание platform_id если не существует
    - Возврат количества успешно вставленных записей
    """
    
    async def save_many(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        reviews: list[EnrichedReview],
        platform_id: UUID | None = None
    ) -> int:
        """
        Массовая вставка отзывов с защитой от дубликатов.
        
        Args:
            db: Async database session
            tenant_id: ID компании (company_id) для мультитенантности
            reviews: Список сырых отзывов после парсинга
            platform_id: UUID платформы (опционально, если None - создаётся автоматически)
            
        Returns:
            int: Количество успешно вставленных записей (не дубликатов)
            
        Raises:
            ValueError: Если reviews пустой список
        """
        if not reviews:
            return 0
        
        # Получаем или создаём platform_id
        if platform_id is None:
            platform_id = await self._get_or_create_platform(
                db, 
                tenant_id, 
                reviews[0].review.platform.value
            )
        
        # Подготовка данных для bulk insert
        review_dicts = []
        for enriched_review in reviews:
            raw_review = enriched_review.review
            review_dict = {
                "company_id": tenant_id,
                "platform_id": platform_id,
                "external_review_id": raw_review.external_id,
                "platform": raw_review.platform.value,
                "author_name": raw_review.author_name,
                "rating": int(raw_review.rating),
                "text": raw_review.text,
                "status": "new",  # ReviewStatus.NEW
                "financial_impact": 0.0,
                "created_at": raw_review.published_at or func.now(),
                "sentiment": (
                    enriched_review.sentiment.value
                    if enriched_review.sentiment is not None
                    else None
                ),
                "tags": list(enriched_review.tags),
                "is_critical": enriched_review.is_critical,
                "auto_reply": enriched_review.reply,
                "ai_pending": enriched_review.ai_pending,
                "ai_error": enriched_review.ai_error,
            }
            review_dicts.append(review_dict)
        
        # Bulk insert с ON CONFLICT DO NOTHING
        stmt = insert(Review).values(review_dicts)
        
        # Индекс для деdupликации: (company_id, platform, external_review_id)
        # Используем constraint или уникальные поля
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["company_id", "platform", "external_review_id"]
        )
        
        # Для подсчёта вставленных записей используем RETURNING
        # Но on_conflict_do_nothing не возвращает конфликтующие строки
        # Поэтому делаем count до и после
        count_before = await self._count_reviews(db, tenant_id)
        
        await db.execute(stmt)
        await db.commit()
        
        count_after = await self._count_reviews(db, tenant_id)
        inserted_count = count_after - count_before
        
        return inserted_count
    
    async def _get_or_create_platform(
        self,
        db: AsyncSession,
        company_id: UUID,
        platform_name: str
    ) -> UUID:
        """
        Получить существующую платформу или создать новую.
        
        Args:
            db: Async database session
            company_id: ID компании
            platform_name: Название платформы (2gis, yandex, google)
            
        Returns:
            UUID: ID платформы
        """
        # Ищем существующую платформу
        stmt = select(Platform).where(
            Platform.company_id == company_id,
            Platform.name == platform_name
        )
        result = await db.execute(stmt)
        platform = result.scalar_one_or_none()
        
        if platform:
            return platform.id
        
        # Создаём новую платформу
        new_platform = Platform(
            company_id=company_id,
            name=platform_name,
            monthly_views=0,
            conversion_rate=0.0,
            cac_on_platform=0.0,
            average_rating=0.0
        )
        db.add(new_platform)
        await db.flush()  # Получаем ID без commit
        
        return new_platform.id
    
    async def _count_reviews(self, db: AsyncSession, tenant_id: UUID) -> int:
        """Подсчёт отзывов для tenant."""
        stmt = select(func.count()).select_from(Review).where(
            Review.company_id == tenant_id
        )
        result = await db.execute(stmt)
        return result.scalar_one()
    
    async def existing_external_ids(
        self, 
        db: AsyncSession, 
        tenant_id: UUID, 
        platform: str, 
        ids: list[str]
    ) -> set[str]:
        """
        Проверяет, какие external_id уже существуют в базе для данного tenant и платформы.
        
        Args:
            db: Async database session
            tenant_id: ID компании (company_id) для изоляции данных
            platform: Название платформы (2gis, yandex, google)
            ids: Список external_id для проверки
            
        Returns:
            set[str]: Множество external_id, которые уже есть в базе
            
        Example:
            >>> existing = await sink.existing_external_ids(
            ...     db, tenant_id, "2gis", ["id1", "id2", "id3"]
            ... )
            >>> print(existing)  # {"id1", "id3"}
        """
        if not ids:
            return set()
        
        # Делаем SELECT external_review_id для проверки существования
        stmt = select(Review.external_review_id).where(
            Review.company_id == tenant_id,
            Review.platform == platform,
            Review.external_review_id.in_(ids)
        )
        
        result = await db.execute(stmt)
        existing_ids = result.scalars().all()
        
        return set(existing_ids)
