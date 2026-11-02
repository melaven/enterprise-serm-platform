"""Shared contracts and registry for external review platform adapters."""

from abc import ABC, abstractmethod
from collections.abc import Callable

AdapterFactory = Callable[[], "BasePlatformAdapter"]


class IntegrationError(Exception):
    """Base error for failures while communicating with a platform."""


class TransientAPIError(IntegrationError):
    """A temporary platform or network failure that should be retried."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class PermanentAPIError(IntegrationError):
    """A non-retryable platform error, such as invalid credentials or input."""


class BasePlatformAdapter(ABC):
    """Interface implemented by platform-specific reply publishers."""

    @abstractmethod
    async def publish_reply(
        self,
        review_external_id: str,
        text: str,
        credentials: dict[str, object],
    ) -> str:
        """Publish a reply and return the platform's external reply identifier."""


class PlatformAdapterRegistry:
    """Register adapter types and create a fresh adapter by platform name."""

    def __init__(self) -> None:
        self._adapter_factories: dict[str, AdapterFactory] = {}

    def register(self, platform: str, adapter_factory: AdapterFactory) -> None:
        normalized_platform = platform.strip().lower()
        if not normalized_platform:
            raise ValueError("Platform name cannot be empty")
        if normalized_platform in self._adapter_factories:
            raise ValueError(f"Adapter already registered for {normalized_platform!r}")
        self._adapter_factories[normalized_platform] = adapter_factory

    def get_adapter(self, platform: str) -> BasePlatformAdapter:
        normalized_platform = platform.strip().lower()
        adapter_factory = self._adapter_factories.get(normalized_platform)
        if adapter_factory is None:
            supported = ", ".join(sorted(self._adapter_factories))
            raise ValueError(
                f"Unsupported platform {platform!r}. Supported platforms: {supported}"
            )
        return adapter_factory()
