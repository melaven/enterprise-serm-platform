"""Тонкий async-клиент к FastAPI-бэкенду (контракт из ТЗ)."""

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from uuid import UUID

import httpx

START_PATH = "/api/v1/parsers/start"
STATUS_PATH = "/api/v1/parsers/status/{job_id}"

COMPLETE_STATUSES = frozenset({"complete", "completed", "done", "success"})
FAILED_STATUSES = frozenset({"failed", "error", "cancelled", "canceled"})


class ApiError(Exception):
    """Ошибка обращения к бэкенду. retryable: имеет смысл повторить опрос."""

    def __init__(
        self, message: str, *, status_code: int | None = None, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class JobStatus:
    status: str  # нормализован: lower-case
    result: Any = None
    error: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.status in COMPLETE_STATUSES

    @property
    def is_failed(self) -> bool:
        return self.status in FAILED_STATUSES


class ApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        api_token: str | None = None,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        headers = {"Accept": "application/json"}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(timeout, connect=5.0),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def start_job(self, url: str, company_id: UUID) -> str:
        data = await self._request(
            "POST", START_PATH, json={"url": url, "company_id": str(company_id)}
        )
        job_id = data.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ApiError("API не вернул job_id")
        return job_id

    async def get_status(self, job_id: str) -> JobStatus:
        # job_id может содержать ':' и другие спецсимволы.
        path = STATUS_PATH.format(job_id=quote(job_id, safe=""))
        data = await self._request("GET", path)
        status = str(data.get("status", "")).strip().lower()
        if not status:
            raise ApiError("API не вернул status")
        result = next(
            (data[k] for k in ("result", "results", "data") if data.get(k) is not None),
            None,
        )
        error = data.get("error") or data.get("detail")
        return JobStatus(
            status=status, result=result, error=str(error) if error else None
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ApiError("API не ответил вовремя", retryable=True) from exc
        except httpx.TransportError as exc:
            raise ApiError(
                "API недоступен (запущен ли uvicorn?)", retryable=True
            ) from exc

        if response.status_code >= 400:
            raise ApiError(
                f"API вернул HTTP {response.status_code}",
                status_code=response.status_code,
                retryable=response.status_code >= 500,
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ApiError("API вернул не-JSON") from exc
        if not isinstance(data, dict):
            raise ApiError("API вернул неожиданный формат ответа")
        return data
