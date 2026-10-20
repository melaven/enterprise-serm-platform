"""Avito platform adapter."""

from datetime import datetime

from app.schemas.parser import RawReview
from app.services.platforms.base import BasePlatformAdapter


class AvitoAdapter(BasePlatformAdapter):
    async def fetch_reviews(self, since: datetime) -> list[RawReview]:
        raise NotImplementedError("Avito review fetching is not implemented")

    async def publish_reply(self, review_id: str, text: str) -> bool:
        raise NotImplementedError("Avito reply publishing is not implemented")
