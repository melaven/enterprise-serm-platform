"""Factory for platform-specific review adapters."""

from collections.abc import Callable

from app.services.platforms.avito import AvitoAdapter
from app.services.platforms.base import BasePlatformAdapter
from app.services.platforms.google import GoogleBusinessAdapter
from app.services.platforms.scraper import OtzovikScraperAdapter
from app.services.platforms.twogis import TwoGisAdapter
from app.services.platforms.yandex import YandexBusinessAdapter

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
        return builder(api_key=api_key, meta_config=meta_config)
