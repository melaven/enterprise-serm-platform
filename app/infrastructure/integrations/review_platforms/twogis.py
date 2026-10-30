"""2GIS platform adapter."""

import logging
from datetime import datetime

from app.api.schemas.parser import RawReview
from app.infrastructure.integrations.review_platforms.base import BasePlatformAdapter

logger = logging.getLogger(__name__)


class TwoGisAdapter(BasePlatformAdapter):
    async def refresh_access_token(self) -> None:
        raise NotImplementedError("2GIS OAuth token refresh is not implemented")

    async def fetch_reviews(self, since: datetime) -> list[RawReview]:
        raise NotImplementedError("2GIS review fetching is not implemented")

    async def publish_reply(self, review_id: str, text: str) -> bool:
        logger.info(
            "Режим SI-Ассистента: текст готов для ручной публикации на площадке %s",
            "2ГИС",
        )
        return True
