"""Common interface for review platform integrations."""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime

from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict

from app.api.schemas.parser import RawReview
from app.core.pii import PIISanitizer, redact_text


class RawPlatformReview(BaseModel):
    """Untrusted review payload returned by a platform integration."""

    model_config = ConfigDict(extra="forbid")

    platform_review_id: str
    author_raw_id: str | None = None
    author_raw_name: str | None = None
    text: str
    rating: float
    published_at: datetime


class SanitizedReview(BaseModel):
    """Review representation safe to pass to downstream storage or LLM services."""

    model_config = ConfigDict(extra="forbid")

    external_id: str
    platform: str
    author_hash: str | None
    author_display: str
    text: str
    rating: float
    published_at: datetime


class BaseReviewAdapter(ABC):
    """Fetch platform reviews and sanitize personal data before exposing them."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the stable platform identifier used to scope author hashes."""

    @abstractmethod
    async def fetch_reviews(
        self, company_id: str, access_token: str
    ) -> list[RawPlatformReview]:
        """Fetch raw reviews for a company using its platform access token."""

    async def get_sanitized_reviews(
        self, company_id: str, access_token: str
    ) -> list[SanitizedReview]:
        """Fetch reviews and remove author identifiers and PII from their text."""
        raw_reviews = await self.fetch_reviews(company_id, access_token)
        sanitized_reviews: list[SanitizedReview] = []
        for review in raw_reviews:
            sanitized_reviews.append(
                await run_in_threadpool(
                    self._sanitize_review, self.platform_name, review
                )
            )
        return sanitized_reviews

    @staticmethod
    def _sanitize_review(
        platform_name: str, review: RawPlatformReview
    ) -> SanitizedReview:
        return SanitizedReview(
            external_id=review.platform_review_id,
            platform=platform_name,
            author_hash=(
                PIISanitizer.hash_user_id(platform_name, review.author_raw_id)
                if review.author_raw_id
                else None
            ),
            author_display=PIISanitizer.mask_author_name(review.author_raw_name),
            text=redact_text(review.text),
            rating=review.rating,
            published_at=review.published_at,
        )


class BasePlatformAdapter(ABC):
    """Base adapter configured with a decrypted API key and platform metadata."""

    def __init__(
        self,
        api_key: str,
        meta_config: dict[str, object],
        refresh_token: str | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        self.api_key = api_key
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.meta_config = deepcopy(meta_config)

    @abstractmethod
    async def fetch_reviews(self, since: datetime) -> list[RawReview]:
        """Fetch reviews created since the given timestamp."""

    @abstractmethod
    async def publish_reply(self, review_id: str, text: str) -> bool:
        """Publish a business reply and return whether the request succeeded."""

    @abstractmethod
    async def refresh_access_token(self) -> None:
        """Refresh OAuth credentials and update this adapter's token state."""
