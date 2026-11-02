"""Yandex Business platform adapter."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import httpx

from app.api.schemas.parser import RawReview
from app.infrastructure.integrations.review_platforms.base import (
    BasePlatformAdapter,
    IntegrationError,
    PermanentAPIError,
    TransientAPIError,
)

_REPLY_API_URL = "https://api.business.yandex.ru/v1/reviews"


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


class YandexBusinessAdapter(BasePlatformAdapter):
    async def refresh_access_token(self) -> None:
        raise NotImplementedError("Yandex OAuth token refresh is not implemented")

    async def fetch_reviews(self, since: datetime) -> list[RawReview]:
        raise NotImplementedError("Yandex review fetching is not implemented")

    async def publish_reply(self, review_id: str, text: str) -> str:
        if not self.api_key:
            raise PermanentAPIError("Yandex Business API key is not configured")

        url = f"{_REPLY_API_URL}/{quote(review_id, safe='')}/replies"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    url,
                    headers={"Authorization": f"OAuth {self.api_key}"},
                    json={"text": text},
                )
        except httpx.TimeoutException as exc:
            raise TransientAPIError("Yandex Business request timed out") from exc
        except httpx.RequestError as exc:
            raise TransientAPIError("Yandex Business request failed") from exc

        if response.status_code == 429 or 500 <= response.status_code < 600:
            raise TransientAPIError(
                f"Yandex Business returned HTTP {response.status_code}",
                retry_after=_parse_retry_after(response.headers.get("Retry-After")),
            )
        if 400 <= response.status_code < 500:
            raise PermanentAPIError(
                f"Yandex Business returned HTTP {response.status_code}",
                status_code=response.status_code,
            )
        if not 200 <= response.status_code < 300:
            raise IntegrationError(
                f"Unexpected Yandex Business HTTP status {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise IntegrationError("Yandex Business returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise IntegrationError("Yandex Business response must be a JSON object")
        external_reply_id = payload.get("external_reply_id")
        if not isinstance(external_reply_id, str) or not external_reply_id:
            raise IntegrationError("Yandex Business response has no external_reply_id")
        return external_reply_id
