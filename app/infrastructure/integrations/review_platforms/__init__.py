"""Platform-specific integrations for fetching reviews and publishing replies."""

from app.infrastructure.integrations.review_platforms.base import BasePlatformAdapter
from app.infrastructure.integrations.review_platforms.factory import (
    PlatformAdapterFactory,
)

__all__ = ["BasePlatformAdapter", "PlatformAdapterFactory"]
