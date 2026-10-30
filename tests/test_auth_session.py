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

from app.api.schemas.auth import JWTPayload
from app.core.auth import (
    AuthConfig,
    decode_token,
    get_current_tenant,
    get_jwt_payload,
)
from app.core.tenant_session import build_rls_claims, tenant_session

SECRET = "x" * 40  # тестовый секрет, не настоящий
CFG = AuthConfig(secret=SECRET, jwks_url=None)
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
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=tok)


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


@pytest.mark.parametrize(
    ("claim", "tenant"),
    [
        ("tenant_id", "not-a-uuid"),
        ("tenant_id", ""),
        ("company_id", "not-a-uuid"),
        ("company_id", ""),
    ],
)
def test_token_with_invalid_tenant_is_401(claim: str, tenant: str) -> None:
    with pytest.raises(HTTPException) as ei:
        run(get_jwt_payload(creds(token(**{claim: tenant})), CFG))
    assert ei.value.status_code == 401
    assert ei.value.detail == "Invalid authentication token: missing tenant context"


def test_missing_tenant_is_rejected_without_falling_back_to_user_id() -> None:
    payload = run(get_jwt_payload(creds(token(tenant_id=None)), CFG))
    assert payload.tenant_id is None
    with pytest.raises(HTTPException) as ei:
        run(get_current_tenant(payload))
    assert ei.value.status_code == 401
    assert ei.value.detail == "Invalid authentication token: missing tenant context"


def test_company_id_claim_is_accepted_as_tenant_context() -> None:
    payload = run(get_jwt_payload(creds(token(tenant_id=None, company_id=TENANT)), CFG))
    assert payload.company_id == UUID(TENANT)
    assert run(get_current_tenant(payload)) == UUID(TENANT)


def test_user_metadata_tenant_is_ignored() -> None:
    tok = token(tenant_id=None, user_metadata={"tenant_id": TENANT})
    payload = run(get_jwt_payload(creds(tok), CFG))
    assert payload.tenant_id is None
    with pytest.raises(HTTPException) as ei:
        run(get_current_tenant(payload))
    assert ei.value.status_code == 401
    assert ei.value.detail == "Invalid authentication token: missing tenant context"


def test_payload_requires_fields() -> None:
    with pytest.raises(ValidationError):
        JWTPayload.model_validate({})


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
    assert "set_config('request.jwt.claims', :claims, true)" in str(stmt)
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
