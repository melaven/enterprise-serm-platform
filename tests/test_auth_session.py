import asyncio
import json
import time
from typing import Any
from uuid import UUID

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from app.core.auth import (
    AuthConfig,
    decode_token,
    get_current_tenant,
    get_jwt_payload,
)
from app.db.session import build_rls_claims, tenant_session
from app.schemas.auth import JWTPayload

SECRET = "x" * 40  # тестовый секрет, не настоящий
CFG = AuthConfig(secret=SECRET)
USER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT = "11111111-1111-1111-1111-111111111111"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def token(**over: Any) -> str:
    claims: dict[str, Any] = {
        "sub": USER,
        "tenant_id": TENANT,
        "aud": "authenticated",
        "exp": int(time.time()) + 600,
        **over,
    }
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, SECRET, algorithm="HS256")


def creds(tok: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials("Bearer", tok)


def test_valid_token() -> None:
    p = decode_token(token(), CFG)
    assert p.tenant_id == UUID(TENANT) and p.sub == UUID(USER)
    assert run(get_current_tenant(p)) == UUID(TENANT)


@pytest.mark.parametrize(
    ("tok", "detail"),
    [
        (token(exp=int(time.time()) - 600), "Token expired"),
        (
            jwt.encode(
                {"sub": USER, "aud": "authenticated", "exp": 9999999999}, "y" * 40
            ),
            "Invalid token",
        ),
        (token(aud="other"), "Invalid token"),
        (token(exp=None), "Invalid token"),  # без exp
        ("garbage", "Invalid token"),
        (
            jwt.encode(
                {"sub": USER, "aud": "authenticated", "exp": 9999999999},
                None,
                algorithm="none",
            ),
            "Invalid token",
        ),
    ],
)
def test_bad_tokens_are_401(tok: str, detail: str) -> None:
    with pytest.raises(HTTPException) as ei:
        run(get_jwt_payload(creds(tok), CFG))
    assert ei.value.status_code == 401 and ei.value.detail == detail


def test_missing_bearer_is_401() -> None:
    with pytest.raises(HTTPException) as ei:
        run(get_jwt_payload(None, CFG))
    assert ei.value.status_code == 401


@pytest.mark.parametrize("tenant", [None, "not-a-uuid", ""])
def test_token_without_valid_tenant_is_403(tenant: str | None) -> None:
    with pytest.raises(HTTPException) as ei:
        run(get_jwt_payload(creds(token(tenant_id=tenant)), CFG))
    assert ei.value.status_code == 403


def test_user_metadata_tenant_is_ignored() -> None:
    tok = token(tenant_id=None, user_metadata={"tenant_id": TENANT})
    with pytest.raises(HTTPException) as ei:
        run(get_jwt_payload(creds(tok), CFG))
    assert ei.value.status_code == 403


def test_payload_requires_fields() -> None:
    with pytest.raises(ValidationError):
        JWTPayload.model_validate({"sub": USER})


def test_claims_json_is_safe_and_minimal() -> None:
    p = decode_token(token(), CFG)
    data = json.loads(build_rls_claims(p))
    assert data == {"sub": USER, "tenant_id": TENANT}


class _Begin:
    def __init__(self, log: list[Any]) -> None:
        self.log = log

    async def __aenter__(self) -> None:
        self.log.append("begin")

    async def __aexit__(self, *exc: Any) -> None:
        self.log.append("commit" if exc[0] is None else "rollback")


class _Session:
    def __init__(self, log: list[Any]) -> None:
        self.log = log

    async def __aenter__(self) -> "_Session":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    def begin(self) -> _Begin:
        return _Begin(self.log)

    async def execute(self, stmt: Any, params: dict[str, str]) -> None:
        self.log.append((stmt, params))


def test_tenant_context_is_first_statement_in_transaction() -> None:
    log: list[Any] = []
    p = decode_token(token(), CFG)

    async def go() -> None:
        async with tenant_session(lambda: _Session(log), p) as s:  # type: ignore[arg-type]
            await s.execute("SELECT 1", {})

    run(go())
    assert log[0] == "begin"
    stmt, params = log[1]
    assert "set_config('request.jwt.claims', :claims, true)" in stmt
    assert json.loads(params["claims"])["tenant_id"] == TENANT
    assert log[2][0] == "SELECT 1" and log[-1] == "commit"


def test_rollback_on_error() -> None:
    log: list[Any] = []
    p = decode_token(token(), CFG)

    async def go() -> None:
        async with tenant_session(lambda: _Session(log), p):  # type: ignore[arg-type]
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        run(go())
    assert log[-1] == "rollback"
