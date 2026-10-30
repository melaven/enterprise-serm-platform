"""Factory for platform-specific review adapters."""

from collections.abc import Callable

from app.infrastructure.integrations.review_platforms.avito import AvitoAdapter
from app.infrastructure.integrations.review_platforms.base import (
    BasePlatformAdapter,
    BaseReviewAdapter,
)
from app.infrastructure.integrations.review_platforms.google import (
    GoogleBusinessAdapter,
)
from app.infrastructure.integrations.review_platforms.mock_adapter import (
    YandexMockAdapter,
)
from app.infrastructure.integrations.review_platforms.scraper import (
    OtzovikScraperAdapter,
)
from app.infrastructure.integrations.review_platforms.twogis import TwoGisAdapter
from app.infrastructure.integrations.review_platforms.yandex import (
    YandexBusinessAdapter,
)

AdapterBuilder = Callable[[str, dict[str, object]], BasePlatformAdapter]

_ADAPTERS: dict[str, AdapterBuilder] = {
    "google": GoogleBusinessAdapter,
    "yandex": YandexBusinessAdapter,
    "2gis": TwoGisAdapter,
    "avito": AvitoAdapter,
    "otzovik": OtzovikScraperAdapter,
}


class PlatformAdapterFactory:
    """Create an uncached adapter instance for a platform integration."""

    @staticmethod
    def get_adapter(
        platform: str,
        api_key: str,
        meta_config: dict[str, object],
    ) -> BasePlatformAdapter:
        builder = _ADAPTERS.get(platform.strip().lower())
        if builder is None:
            supported = ", ".join(sorted(_ADAPTERS))
            raise ValueError(
                f"Unsupported platform {platform!r}. Supported platforms: {supported}"
            )
        return builder(api_key, meta_config)


def get_adapter(platform: str) -> BaseReviewAdapter:
    """Get a review adapter for the specified platform.
    
    Args:
        platform: Platform identifier (e.g., "yandex", "google")
        
    Returns:
        BaseReviewAdapter instance for the platform
        
    Raises:
        ValueError: If platform is not supported
    """
    platform_lower = platform.strip().lower()
    
    if platform_lower == "yandex":
        return YandexMockAdapter()
    
    supported = ["yandex"]
    raise ValueError(
        f"Unsupported platform {platform!r}. Supported platforms: {', '.join(supported)}"
    )
