"""Platform-specific integrations for fetching reviews and publishing replies."""

from app.services.platforms.base import BasePlatformAdapter
from app.services.platforms.factory import PlatformAdapterFactory

__all__ = ["BasePlatformAdapter", "PlatformAdapterFactory"]
