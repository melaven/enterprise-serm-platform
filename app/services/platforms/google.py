"""Google Business platform adapter."""

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx

from app.core.config import get_settings
from app.schemas.parser import Platform, RawReview
from app.services.platforms.base import BasePlatformAdapter

_STAR_RATINGS = {
    "STAR_RATING_ONE": 1,
    "STAR_RATING_TWO": 2,
    "STAR_RATING_THREE": 3,
    "STAR_RATING_FOUR": 4,
    "STAR_RATING_FIVE": 5,
}
_MAX_REVIEW_PAGES = 100


class GoogleBusinessAdapter(BasePlatformAdapter):
    async def refresh_access_token(self) -> None:
        if not self.refresh_token:
            raise ValueError("Google OAuth refresh token is not configured")
        settings = get_settings()
        if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
            raise ValueError("Google OAuth client credentials are not configured")

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret.get_secret_value(),
                },
            )
            response.raise_for_status()
            token_data = response.json()

        if not isinstance(token_data, dict):
            raise ValueError("Google OAuth refresh response is not an object")
        access_token = token_data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("Google OAuth refresh response has no access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")
        if (
            not isinstance(expires_in, int | float)
            or isinstance(expires_in, bool)
            or expires_in <= 0
        ):
            raise ValueError("Google OAuth refresh response has invalid expires_in")
        self.api_key = access_token
        if isinstance(refresh_token, str) and refresh_token:
            self.refresh_token = refresh_token
        self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    async def fetch_reviews(self, since: datetime) -> list[RawReview]:
        account_id = self.meta_config.get("external_account_id")
        location_id = self.meta_config.get("external_location_id")
        if not isinstance(account_id, str) or not account_id:
            raise ValueError("Missing external_account_id in meta_config")
        if not isinstance(location_id, str) or not location_id:
            raise ValueError("Missing external_location_id in meta_config")

        url = (
            "https://mybusiness.googleapis.com/v4/accounts/"
            f"{quote(account_id, safe='')}/locations/{quote(location_id, safe='')}/reviews"
        )
        normalized_since = since.astimezone(timezone.utc)
        reviews: list[RawReview] = []
        page_token: str | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            for page_number in range(_MAX_REVIEW_PAGES):
                params: dict[str, str | int] = {"pageSize": 50}
                if page_token:
                    params["pageToken"] = page_token
                response = await client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if response.status_code == 401 and page_number == 0:
                    await self.refresh_access_token()
                    response = await client.get(
                        url,
                        params=params,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Google Business reviews response is not an object")
                page_reviews = payload.get("reviews", [])
                if not isinstance(page_reviews, list):
                    raise ValueError("Google Business reviews field is not a list")

                for item in page_reviews:
                    if not isinstance(item, dict):
                        raise ValueError("Google Business review entry is not an object")
                    review_id = item.get("reviewId")
                    create_time = item.get("createTime")
                    rating = _STAR_RATINGS.get(item.get("starRating"))
                    if not isinstance(review_id, str) or not review_id:
                        raise ValueError("Google Business review has no reviewId")
                    if not isinstance(create_time, str):
                        raise ValueError("Google Business review has no createTime")
                    if rating is None:
                        raise ValueError(
                            "Google Business review has an unsupported rating"
                        )
                    published_at = datetime.fromisoformat(
                        create_time.replace("Z", "+00:00")
                    )
                    if published_at.tzinfo is None:
                        published_at = published_at.replace(tzinfo=timezone.utc)
                    published_at = published_at.astimezone(timezone.utc)
                    if published_at < normalized_since:
                        continue

                    comment = item.get("comment", "")
                    if not isinstance(comment, str):
                        raise ValueError("Google Business review comment is not text")
                    reviews.append(
                        RawReview(
                            platform_id=review_id,
                            author_name="Автор отзыва",
                            text=comment,
                            rating=rating,
                            date=published_at,
                            platform=Platform.GOOGLE,
                        )
                    )

                page_token = payload.get("nextPageToken")
                if page_token is None:
                    return reviews
                if not isinstance(page_token, str) or not page_token:
                    raise ValueError("Google Business nextPageToken is invalid")

        raise RuntimeError(
            f"Google Business pagination exceeded {_MAX_REVIEW_PAGES} pages"
        )

    async def publish_reply(self, review_id: str, text: str) -> bool:
        raise RuntimeError(
            "Reply publishing is disabled; a human must review and publish drafts"
        )
