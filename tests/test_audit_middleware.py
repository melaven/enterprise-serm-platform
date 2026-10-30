import time
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI, Request, Response

from app.api.v1.routes import webhooks_config
from app.core import audit_middleware
from app.core.audit_middleware import SecurityAuditMiddleware
from app.core.auth import AuthConfig, get_auth_config, get_current_tenant


class FakeAuditSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.closed = 0

    def add(self, row: object) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None

    async def close(self) -> None:
        self.closed += 1


@pytest_asyncio.fixture
async def audit_app(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[httpx.AsyncClient, FakeAuditSession, FakeAuditSession, UUID, UUID]:
    tenant_id = uuid4()
    user_id = uuid4()
    audit_session = FakeAuditSession()
    webhook_session = FakeAuditSession()

    async def get_audit_session(**kwargs: object) -> FakeAuditSession:
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["user_id"] == user_id
        return audit_session

    async def get_webhook_tenant_session(**kwargs: object) -> FakeAuditSession:
        assert kwargs["tenant_id"] == tenant_id
        return webhook_session

    monkeypatch.setattr(audit_middleware, "get_tenant_session", get_audit_session)
    monkeypatch.setattr(
        webhooks_config, "get_tenant_session", get_webhook_tenant_session
    )
    app = FastAPI()
    app.add_middleware(SecurityAuditMiddleware)
    app.dependency_overrides[get_auth_config] = lambda: AuthConfig(
        secret="audit-test-secret-key-long-enough-for-hs256",
        jwks_url=None,
    )

    @app.delete("/api/v1/webhooks/{endpoint_id}")
    async def delete_webhook(
        request: Request,
        endpoint_id: str,
        verified_tenant: UUID = Depends(get_current_tenant),
        session: FakeAuditSession = Depends(webhooks_config.get_webhook_session),
    ) -> Response:
        assert verified_tenant == tenant_id
        return Response(status_code=204)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, webhook_session, audit_session, tenant_id, user_id


@pytest.mark.asyncio
async def test_successful_webhook_delete_is_audited_with_actor_and_ip(
    audit_app: tuple[httpx.AsyncClient, FakeAuditSession, FakeAuditSession, UUID, UUID],
) -> None:
    client, webhook_session, audit_session, tenant_id, user_id = audit_app
    endpoint_id = uuid4()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "aud": "authenticated",
            "exp": int(time.time()) + 60,
        },
        "audit-test-secret-key-long-enough-for-hs256",
        algorithm="HS256",
    )

    response = await client.delete(
        f"/api/v1/webhooks/{endpoint_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204
    assert webhook_session.commits == 1
    assert audit_session.commits == 1
    audit_row = audit_session.added[0]
    assert audit_row.tenant_id == tenant_id
    assert audit_row.user_id == user_id
    assert audit_row.action == "webhook.delete"
    assert audit_row.ip_address == "127.0.0.1"
    assert audit_session.closed == 1


@pytest.mark.asyncio
async def test_non_sensitive_route_is_not_audited(
    audit_app: tuple[httpx.AsyncClient, FakeAuditSession, FakeAuditSession, UUID, UUID],
) -> None:
    client, _, audit_session, _, _ = audit_app

    response = await client.get("/not-a-sensitive-action")

    assert response.status_code == 404
    assert audit_session.added == []
    assert audit_session.commits == 0
