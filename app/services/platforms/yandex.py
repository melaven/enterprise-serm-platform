"""Yandex Business platform adapter."""

from datetime import datetime

import httpx

from app.schemas.parser import RawReview
from app.services.platforms.base import BasePlatformAdapter


class YandexBusinessAdapter(BasePlatformAdapter):
    async def fetch_reviews(self, since: datetime) -> list[RawReview]:
        raise NotImplementedError("Yandex review fetching is not implemented")

    async def publish_reply(self, review_id: str, text: str) -> bool:
        org_id = self.meta_config.get("yandex_org_id")
        if not org_id:
            raise ValueError("Missing yandex_org_id in meta_config")

        url = f"https://api.yandex.ru/v1/orgs/{org_id}/reviews/" f"{review_id}/replies"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={"text": text},
                headers={"Authorization": f"OAuth {self.api_key}"},
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                return False
            return response.is_success
