import os
from uuid import uuid4

import pytest
from sqlalchemy import make_url, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


def _test_database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    url = make_url(database_url)
    database_name = url.database or ""
    if not (database_name.endswith("_test") or database_name.startswith("test_")):
        pytest.fail(
            "TEST_DATABASE_URL must point to a test database "
            f"(*_test or test_*), got {database_name!r}"
        )
    if not url.drivername.startswith("postgresql"):
        pytest.fail("Audit trigger integration test requires PostgreSQL")
    return database_url


@pytest.mark.asyncio
async def test_review_update_is_written_to_audit_logs_with_actor_and_snapshots() -> (
    None
):
    engine = create_async_engine(_test_database_url(), poolclass=NullPool)
    try:
        try:
            connection = await engine.connect()
        except (OSError, SQLAlchemyError) as exc:
            pytest.skip(f"PostgreSQL test database is unavailable: {exc}")

        try:
            transaction = await connection.begin()
            try:
                trigger_installed = await connection.scalar(
                    text(
                        "SELECT EXISTS ("
                        "SELECT 1 FROM pg_trigger "
                        "WHERE tgrelid = 'public.reviews'::regclass "
                        "AND tgname = 'audit_log_changes' "
                        "AND NOT tgisinternal)"
                    )
                )
                if not trigger_installed:
                    pytest.fail("Run migration 047 before the audit trigger test")

                user_id = uuid4()
                company_id = uuid4()
                review_id = uuid4()
                old_text = "Положительный отзыв; оценка 5/5."
                new_text = "Нейтральный отзыв; оценка 5/5."
                await connection.execute(
                    text(
                        "SELECT set_config('app.company_id', :company_id, true), "
                        "set_config('app.user_id', :user_id, true), "
                        "set_config('app.current_user_id', :user_id, true)"
                    ),
                    {"company_id": str(company_id), "user_id": str(user_id)},
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.companies (id, name) "
                        "VALUES (:company_id, 'audit trigger test')"
                    ),
                    {"company_id": company_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.reviews "
                        "(id, company_id, author_name, rating, text) "
                        "VALUES (:review_id, :company_id, 'Автор отзыва', 5, :text)"
                    ),
                    {
                        "review_id": review_id,
                        "company_id": company_id,
                        "text": old_text,
                    },
                )
                await connection.execute(
                    text(
                        "UPDATE public.reviews SET text = :new_text "
                        "WHERE id = :review_id AND company_id = :company_id"
                    ),
                    {
                        "new_text": new_text,
                        "review_id": review_id,
                        "company_id": company_id,
                    },
                )

                audit = (
                    (
                        await connection.execute(
                            text(
                                "SELECT old_data, new_data, changed_by_user_id "
                                "FROM public.audit_logs "
                                "WHERE table_name = 'reviews' "
                                "AND record_id = :review_id AND action = 'UPDATE' "
                                "AND changed_by_user_id = :user_id "
                                "AND new_data ->> 'text' = :new_text "
                                "ORDER BY created_at DESC LIMIT 1"
                            ),
                            {
                                "review_id": review_id,
                                "user_id": user_id,
                                "new_text": new_text,
                            },
                        )
                    )
                    .mappings()
                    .one()
                )

                assert audit["old_data"]["text"] == old_text
                assert audit["new_data"]["text"] == new_text
                assert audit["changed_by_user_id"] == user_id
            finally:
                await transaction.rollback()
        finally:
            await connection.close()
    finally:
        await engine.dispose()
