"""Manual-publication adapter for Otzovik."""

import logging
from datetime import datetime

from app.schemas.parser import RawReview
from app.services.platforms.base import BasePlatformAdapter

logger = logging.getLogger(__name__)


class OtzovikScraperAdapter(BasePlatformAdapter):
    async def refresh_access_token(self) -> None:
        raise NotImplementedError("Otzovik OAuth token refresh is not implemented")

    async def fetch_reviews(self, since: datetime) -> list[RawReview]:
        raise NotImplementedError("Otzovik review fetching is not implemented")

    async def publish_reply(self, review_id: str, text: str) -> bool:
        logger.info(
            "Режим SI-Ассистента: текст готов для ручной публикации на площадке %s",
            "Отзовик",
        )
        return True
