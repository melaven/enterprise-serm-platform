"""Фабрика парсеров."""

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.schemas.parser import Platform
from app.services.parsers.base import BaseReviewParser, UnsupportedPlatformError
from app.services.parsers.twogis import TwoGisParser


@dataclass(frozen=True, slots=True)
class ParserDeps:
    """Зависимости парсеров (кладутся в ctx воркера при старте)."""

    http_client: httpx.AsyncClient | None = None
    twogis_api_key: str = ""


def _make_twogis(deps: ParserDeps) -> BaseReviewParser:
    return TwoGisParser(api_key=deps.twogis_api_key, client=deps.http_client)


# Яндекс и Google: добавь реализацию и строку в реестр.
_REGISTRY: dict[Platform, Callable[[ParserDeps], BaseReviewParser]] = {
    Platform.TWOGIS: _make_twogis,
}


def create_parser(platform: str, deps: ParserDeps) -> BaseReviewParser:
    try:
        kind = Platform(platform)
    except ValueError as exc:
        raise UnsupportedPlatformError(f"unknown platform: {platform!r}") from exc
    builder = _REGISTRY.get(kind)
    if builder is None:
        raise UnsupportedPlatformError(f"no parser implemented for {platform!r}")
    return builder(deps)
