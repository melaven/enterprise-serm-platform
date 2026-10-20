"""Google Business platform adapter."""

from datetime import datetime

from app.schemas.parser import RawReview
from app.services.platforms.base import BasePlatformAdapter


class GoogleBusinessAdapter(BasePlatformAdapter):
    async def fetch_reviews(self, since: datetime) -> list[RawReview]:
        raise NotImplementedError("Google Business review fetching is not implemented")

    async def publish_reply(self, review_id: str, text: str) -> bool:
        raise NotImplementedError("Google Business reply publishing is not implemented")
