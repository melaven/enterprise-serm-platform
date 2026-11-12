from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from scripts import seed_demo


def test_provision_demo_auth_user_creates_confirmed_tenant_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    create_user = Mock(return_value=SimpleNamespace(user=SimpleNamespace(id=user_id)))
    admin = SimpleNamespace(
        list_users=lambda **_: [],
        create_user=create_user,
    )
    client = SimpleNamespace(auth=SimpleNamespace(admin=admin))
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    monkeypatch.setattr(seed_demo, "create_client", lambda *_: client)

    assert seed_demo.provision_demo_auth_user() == user_id
    assert create_user.call_args.args[0] == {
        "email": seed_demo.DEMO_USER_EMAIL,
        "password": seed_demo.DEMO_USER_PASSWORD,
        "email_confirm": True,
        "user_metadata": {"tenant_id": str(seed_demo.DEMO_TENANT_ID)},
    }


def test_provision_demo_auth_user_requires_service_role_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
        seed_demo.provision_demo_auth_user()


@pytest.mark.asyncio
async def test_create_demo_user_casts_raw_user_metadata_as_jsonb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    execute = AsyncMock()
    connection = SimpleNamespace(execute=execute)

    class _Transaction:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, *_args):
            return None

    admin_engine = SimpleNamespace(
        begin=lambda: _Transaction(),
        dispose=AsyncMock(),
    )
    monkeypatch.setattr(seed_demo, "provision_demo_auth_user", lambda: user_id)
    monkeypatch.setattr(seed_demo, "admin_database_url", lambda: "test-dsn")
    monkeypatch.setattr(
        seed_demo, "create_async_engine", lambda *_args, **_kwargs: admin_engine
    )

    await seed_demo.create_demo_user()

    metadata_statement, metadata_params = execute.await_args_list[0].args
    assert "CAST(:user_metadata AS jsonb)" in str(metadata_statement)
    assert metadata_params["user_metadata"] == (
        f'{{"tenant_id": "{seed_demo.DEMO_TENANT_ID}"}}'
    )
