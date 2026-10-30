from datetime import datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class Platform(StrEnum):
    TWOGIS = "2gis"
    YANDEX = "yandex"
    GOOGLE = "google"
    TRUSTPILOT = "trustpilot"


# SSRF-защита: воркер ходит по URL из запроса, поэтому хост ограничен доменами площадки.
ALLOWED_HOSTS: dict[Platform, tuple[str, ...]] = {
    Platform.TWOGIS: ("2gis.ru", "2gis.com"),
    Platform.YANDEX: ("yandex.ru", "yandex.com"),
    Platform.GOOGLE: ("google.com", "maps.app.goo.gl", "g.page"),
    Platform.TRUSTPILOT: ("trustpilot.com",),
}


def host_allowed(url: str, platform: Platform) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith(f".{d}") for d in ALLOWED_HOSTS[platform])


class ParseStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: Platform
    url: HttpUrl

    @model_validator(mode="after")
    def _host_matches_platform(self) -> "ParseStartRequest":
        if not host_allowed(str(self.url), self.platform):
            raise ValueError(f"URL host does not belong to {self.platform.value}")
        return self


class ParseStartResponse(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"


class ParseJobPayload(BaseModel):
    """Контракт API → воркер. tenant_id берётся ТОЛЬКО из проверенного JWT."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: UUID
    platform: Platform
    url: str
    max_reviews: int = Field(ge=1, le=5000)
    requested_at: datetime


class ParseResult(BaseModel):
    reviews_found: int  # собрано скрейпером
    reviews_new: int  # из них ещё не было в БД
    reviews_saved: int  # реально вставлено
    ai_enriched: int
    ai_pending: int  # ушли в БД без разметки, добьёт retry_pending_ai_reviews
    duration_ms: int


class ParseJobState(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NOT_FOUND = "not_found"


class ParseJobStatus(BaseModel):
    job_id: str
    state: ParseJobState
    result: ParseResult | None = None
    error: str | None = None
