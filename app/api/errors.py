"""API-specific exceptions and response handlers."""

from fastapi import Request, status
from fastapi.responses import JSONResponse


class DuplicateWebhookError(Exception):
    """Raised when an external platform webhook has already been accepted."""


async def duplicate_webhook_exception_handler(
    _request: Request,
    _exc: DuplicateWebhookError,
) -> JSONResponse:
    """Acknowledge duplicates so webhook providers do not retry them."""
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "accepted", "duplicate": True},
    )
