"""2GIS platform adapter."""

from datetime import datetime

from app.schemas.parser import RawReview
from app.services.platforms.base import BasePlatformAdapter


class TwoGisAdapter(BasePlatformAdapter):
    async def fetch_reviews(self, since: datetime) -> list[RawReview]:
        raise NotImplementedError("2GIS review fetching is not implemented")

    async def publish_reply(self, review_id: str, text: str) -> bool:
        raise NotImplementedError("2GIS reply publishing is not implemented")
