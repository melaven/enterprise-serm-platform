from collections.abc import Sequence

from app.repositories.review_repository import ReviewRepository
from app.services.pii import redact_text
from app.services.scrapers import RawReviewSchema


class ReviewIngestService:
    def __init__(self, repo: ReviewRepository) -> None:
        self._repo = repo

    async def store(
        self, *, platform: str, url: str, reviews: Sequence[RawReviewSchema]
    ) -> int:
        """Сохраняет отзывы; возвращает число реально добавленных (без дублей)."""
        rows = [
            {
                "platform": platform,
                "external_id": r.external_id,
                "author_name": r.author_name,
                "rating": r.rating,
                # 152-ФЗ: ПДн вырезаются ДО записи в БД (детерминированно, без LLM): телефоны, email и т.п.
                # не попадают в хранилище даже если анализ позже упадёт или не запустится.
                "text": redact_text(r.text) if r.text else r.text,
                "published_at": r.published_at,
                "reply_text": redact_text(r.reply_text) if r.reply_text else r.reply_text,
                # ORM-атрибут `metadata` зарезервирован Declarative Base,
                # поэтому колонка называется raw_metadata.
                "raw_metadata": r.metadata,
                "source_url": url,
            }
            for r in reviews
        ]
        return await self._repo.add_many_ignore_duplicates(rows)
