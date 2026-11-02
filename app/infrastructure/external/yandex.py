"""Yandex Business reply publisher."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import httpx

from app.infrastructure.external.base import (
    BasePlatformAdapter,
    IntegrationError,
    PermanentAPIError,
    TransientAPIError,
)

_API_BASE_URL = "https://api.business.yandex.ru/v1/reviews"
_REQUEST_TIMEOUT = 20.0


def _retry_after_seconds(value: str | None) -> float | None:
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
    """Publish a reply using the Yandex Business reviews API."""

    async def publish_reply(
        self,
        review_external_id: str,
        text: str,
        credentials: dict[str, object],
    ) -> str:
        access_token = credentials.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise PermanentAPIError("Yandex credentials require an access_token")

        url = f"{_API_BASE_URL}/{quote(review_external_id, safe='')}/replies"
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                response = await client.post(
                    url,
                    headers={"Authorization": f"OAuth {access_token}"},
                    json={"text": text},
                )
        except httpx.TimeoutException as exc:
            raise TransientAPIError("Yandex Business request timed out") from exc
        except httpx.RequestError as exc:
            raise TransientAPIError("Yandex Business request failed") from exc

        if response.status_code == 429 or 500 <= response.status_code < 600:
            raise TransientAPIError(
                f"Yandex Business returned HTTP {response.status_code}",
                retry_after=_retry_after_seconds(response.headers.get("Retry-After")),
            )
        if 400 <= response.status_code < 500:
            raise PermanentAPIError(
                f"Yandex Business returned HTTP {response.status_code}"
            )
        if not 200 <= response.status_code < 300:
            raise IntegrationError(
                f"Unexpected Yandex Business HTTP status {response.status_code}"
            )

        try:
            response_payload = response.json()
        except ValueError as exc:
            raise IntegrationError(
                "Yandex Business returned an invalid JSON response"
            ) from exc
        if not isinstance(response_payload, dict):
            raise IntegrationError("Yandex Business response must be a JSON object")

        external_reply_id = response_payload.get("external_reply_id")
        if not isinstance(external_reply_id, str) or not external_reply_id:
            raise IntegrationError("Yandex Business response has no external_reply_id")
        return external_reply_id
