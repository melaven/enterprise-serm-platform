from uuid import uuid4

import pytest
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    Table,
    event,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.schemas.auth import JWTPayload
from app.core.auth import tenant_id_from_payload
from app.core.tenant_session import (
    RLS_CONTEXT_INFO_KEY,
    set_tenant_rls_context,
    tenant_session,
)


def _register_set_config(engine, applied_settings: list[tuple[str, str, bool]]) -> None:
    def set_config(name: str, value: str, is_local: bool) -> str:
        applied_settings.append((name, value, is_local))
        return value

    @event.listens_for(engine.sync_engine, "connect")
    def register_set_config(connection, _record) -> None:
        connection.run_async(
            lambda raw_connection: raw_connection.create_function(
                "set_config", 3, set_config
            )
        )


@pytest.mark.asyncio
async def test_tenant_session_applies_rls_context_before_first_query() -> None:
    applied_settings: list[tuple[str, str, bool]] = []
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _register_set_config(engine, applied_settings)
    tenant_id = uuid4()
    user_id = uuid4()
    payload = JWTPayload(sub=user_id, tenant_id=tenant_id)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with tenant_session(session_factory, payload) as session:
            assert applied_settings == []
            assert await session.scalar(text("SELECT 1")) == 1

        assert [setting[0] for setting in applied_settings] == [
            "request.jwt.claims",
            "app.company_id",
            "app.user_id",
            "app.current_user_id",
        ]
        assert all(is_local for _, _, is_local in applied_settings)
        assert tenant_id_from_payload(payload) == tenant_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_rls_context_is_restored_after_commit_on_same_session() -> None:
    applied_settings: list[tuple[str, str, bool]] = []
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _register_set_config(engine, applied_settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    tenant_id = uuid4()
    user_id = uuid4()

    try:
        async with session_factory() as session:
            await set_tenant_rls_context(session, tenant_id, user_id)
            assert applied_settings == []
            assert session.sync_session.info[RLS_CONTEXT_INFO_KEY] == {
                "claims": f'{{"sub": "{user_id}", "tenant_id": "{tenant_id}"}}',
                "company_id": str(tenant_id),
                "user_id": str(user_id),
                "current_user_id": str(user_id),
            }

            await session.execute(text("SELECT 1"))
            assert len(applied_settings) == 4

            await session.commit()
            await session.execute(text("SELECT 1"))

            assert len(applied_settings) == 8
            assert applied_settings[4:] == applied_settings[:4]
            assert all(is_local for _, _, is_local in applied_settings)
            assert applied_settings[3] == (
                "app.current_user_id",
                str(user_id),
                True,
            )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("statement_kind", ["update", "select"])
@pytest.mark.asyncio
async def test_tenant_dependency_commits_only_session_dml(
    monkeypatch: pytest.MonkeyPatch,
    statement_kind: str,
) -> None:
    from app.core import dependencies

    applied_settings: list[tuple[str, str, bool]] = []
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _register_set_config(engine, applied_settings)
    metadata = MetaData()
    records = Table(
        "records",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", Integer, nullable=False),
    )
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
        await connection.execute(records.insert().values(id=1, value=10))

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(dependencies, "AsyncSessionLocal", session_factory)
    payload = JWTPayload(sub=uuid4(), tenant_id=uuid4())
    commits: list[str] = []

    try:
        generator = dependencies.get_tenant_db(payload=payload)
        session = await anext(generator)
        event.listen(
            session.sync_session,
            "after_commit",
            lambda _session: commits.append("commit"),
        )

        if statement_kind == "update":
            await session.execute(update(records).values(value=20))
        else:
            await session.execute(select(records))

        with pytest.raises(StopAsyncIteration):
            await generator.asend(None)

        assert commits == (["commit"] if statement_kind == "update" else [])
        assert [setting[0] for setting in applied_settings] == [
            "request.jwt.claims",
            "app.company_id",
            "app.user_id",
            "app.current_user_id",
        ]

        async with session_factory() as verification_session:
            value = await verification_session.scalar(
                select(records.c.value).where(records.c.id == 1)
            )
        assert value == (20 if statement_kind == "update" else 10)
    finally:
        await engine.dispose()
