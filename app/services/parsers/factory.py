"""Фабрика парсеров."""

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.schemas.parser import Platform
from app.services.parsers.base import BaseReviewParser, UnsupportedPlatformError


@dataclass(frozen=True, slots=True)
class ParserDeps:
    """Зависимости парсеров (кладутся в ctx воркера при старте)."""

    http_client: httpx.AsyncClient | None = None
    twogis_api_key: str = ""


_REGISTRY: dict[Platform, Callable[[ParserDeps], BaseReviewParser]] = {}


def create_parser(platform: str, deps: ParserDeps) -> BaseReviewParser:
    try:
        kind = Platform(platform)
    except ValueError as exc:
        raise UnsupportedPlatformError(f"unknown platform: {platform!r}") from exc
    builder = _REGISTRY.get(kind)
    if builder is None:
        raise UnsupportedPlatformError(
            "Public-page review scraping is disabled; no authorized official "
            f"parser is configured for {platform!r}"
        )
    return builder(deps)
