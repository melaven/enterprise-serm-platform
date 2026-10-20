"""Common interface for review platform integrations."""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime

from app.schemas.parser import RawReview


class BasePlatformAdapter(ABC):
    """Base adapter configured with a decrypted API key and platform metadata."""

    def __init__(self, api_key: str, meta_config: dict[str, object]) -> None:
        self.api_key = api_key
        self.meta_config = deepcopy(meta_config)

    @abstractmethod
    async def fetch_reviews(self, since: datetime) -> list[RawReview]:
        """Fetch reviews created since the given timestamp."""

    @abstractmethod
    async def publish_reply(self, review_id: str, text: str) -> bool:
        """Publish a business reply and return whether the request succeeded."""
