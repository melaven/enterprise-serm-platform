from urllib.parse import urlencode

import pytest
from starlette.requests import Request
from starlette.routing import Mount

from app.api.admin import (
    AdminAuthenticationBackend,
    CompanyAdmin,
    PlatformAdmin,
    ReviewAdmin,
    ReviewReplyAdmin,
)
from app.main import admin, app


def test_admin_is_mounted_with_all_model_views() -> None:
    assert any(
        isinstance(route, Mount) and route.path == "/admin" for route in app.routes
    )
    assert {view.model for view in admin._views} == {
        CompanyAdmin.model,
        PlatformAdmin.model,
        ReviewAdmin.model,
        ReviewReplyAdmin.model,
    }


def test_review_long_text_is_only_in_details() -> None:
    assert [column.key for column in ReviewAdmin.column_list] == [
        "id",
        "company_id",
        "platform_id",
        "moderation_status",
        "rating",
    ]
    assert "text" in [column.key for column in ReviewAdmin.column_details_list]
    assert "reply_text" not in [column.key for column in ReviewReplyAdmin.column_list]
    assert "reply_text" in [
        column.key for column in ReviewReplyAdmin.column_details_list
    ]


@pytest.mark.asyncio
async def test_admin_authentication_uses_configured_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "p@ss&w0rd")
    monkeypatch.setenv("ADMIN_SECRET_KEY", "test-session-secret")
    backend = AdminAuthenticationBackend()

    body = urlencode({"username": "admin", "password": "p@ss&w0rd"}).encode()

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/admin/login",
            "raw_path": b"/admin/login",
            "query_string": b"",
            "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
            "client": ("test", 1),
            "server": ("test", 80),
            "session": {},
        },
        receive,
    )

    assert await backend.login(request)
    assert await backend.authenticate(request)
    await backend.logout(request)
    assert not await backend.authenticate(request)
