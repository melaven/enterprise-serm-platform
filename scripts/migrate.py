"""Apply the ordered PostgreSQL migrations transactionally."""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MIGRATIONS_DIR = ROOT / "migrations"
MIGRATIONS: Final = (
    "000_local_core_schema.sql",
    "001_multitenancy_rls.sql",
    "002_custom_access_token_hook.sql",
    "003_rls_smoke_test.sql",
    "004_reviews_dedup.sql",
    "005_llm_analytics.sql",
    "006_dead_letter_queue.sql",
    "008_billing_quotas.sql",
    "009_billing_seed.sql",
    "010_reviews_ai_fields.sql",
    "011_reputation_data.sql",
    "012_llm_cache.sql",
    "014_rename_quotas_table.sql",
    "015_quota_service_contract.sql",
    "016_admin_quota_updates.sql",
)
_DOLLAR_TAG = re.compile(r"\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$")
_TRANSACTION_COMMANDS = {"BEGIN", "COMMIT", "ROLLBACK"}


def split_sql_statements(sql: str) -> list[str]:
    """Split SQL on top-level semicolons, preserving quoted and procedural bodies."""
    statements: list[str] = []
    current: list[str] = []
    index = 0
    length = len(sql)
    quote: str | None = None
    dollar_tag: str | None = None
    block_comment_depth = 0
    line_comment = False
    escape_string = False

    while index < length:
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < length else ""

        if line_comment:
            current.append(char)
            if char == "\n":
                line_comment = False
            index += 1
            continue

        if block_comment_depth:
            current.append(char)
            if char == "/" and next_char == "*":
                current.append(next_char)
                block_comment_depth += 1
                index += 2
            elif char == "*" and next_char == "/":
                current.append(next_char)
                block_comment_depth -= 1
                index += 2
            else:
                index += 1
            continue

        if dollar_tag is not None:
            if sql.startswith(dollar_tag, index):
                current.append(dollar_tag)
                index += len(dollar_tag)
                dollar_tag = None
            else:
                current.append(char)
                index += 1
            continue

        if quote is not None:
            current.append(char)
            if escape_string and char == "\\":
                if next_char:
                    current.append(next_char)
                    index += 2
                else:
                    index += 1
            elif char == quote:
                if next_char == quote:
                    current.append(next_char)
                    index += 2
                else:
                    quote = None
                    index += 1
            else:
                index += 1
            continue

        if char == "-" and next_char == "-":
            current.extend((char, next_char))
            line_comment = True
            index += 2
        elif char == "/" and next_char == "*":
            current.extend((char, next_char))
            block_comment_depth = 1
            index += 2
        elif char in {"'", '"'}:
            quote = char
            escape_string = (
                char == "'"
                and index > 0
                and sql[index - 1] in {"e", "E"}
                and (
                    index < 2 or not (sql[index - 2].isalnum() or sql[index - 2] == "_")
                )
            )
            current.append(char)
            index += 1
        elif char == "$":
            match = _DOLLAR_TAG.match(sql, index)
            if match:
                dollar_tag = match.group()
                current.append(dollar_tag)
                index += len(dollar_tag)
            else:
                current.append(char)
                index += 1
        elif char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current.clear()
            index += 1
        else:
            current.append(char)
            index += 1

    if quote is not None or dollar_tag is not None or block_comment_depth:
        raise ValueError(
            "Unterminated SQL quoted string, dollar-quoted body, or comment"
        )

    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)
    return statements


def migration_statements(sql: str) -> list[str]:
    """Remove script-level transaction wrappers; the runner owns transactions."""
    result = []
    for statement in split_sql_statements(sql):
        without_comments = re.sub(
            r"^(?:\s|--[^\n]*(?:\n|$)|/\*.*?\*/)*",
            "",
            statement,
            flags=re.DOTALL,
        )
        if without_comments.strip().upper() not in _TRANSACTION_COMMANDS:
            result.append(statement)
    return result


async def _migration_engine():
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL must point to the local PostgreSQL admin role."
        )

    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")
    elif url.drivername != "postgresql+asyncpg":
        raise RuntimeError("DATABASE_URL must use PostgreSQL with asyncpg.")

    return create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
    )


async def apply_migrations() -> None:
    from sqlalchemy import text

    engine = await _migration_engine()
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS public.serm_schema_migrations (
                        version varchar(128) PRIMARY KEY,
                        applied_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
            )

        for filename in MIGRATIONS:
            path = MIGRATIONS_DIR / filename
            if not path.is_file():
                raise FileNotFoundError(f"Required migration is missing: {path}")
            version = path.stem

            async with engine.begin() as connection:
                await connection.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:lock_name)::bigint)"),
                    {"lock_name": "tenable-serm-schema-migrations"},
                )
                already_applied = await connection.scalar(
                    text(
                        "SELECT EXISTS ("
                        "SELECT 1 FROM public.serm_schema_migrations "
                        "WHERE version = :version)"
                    ),
                    {"version": version},
                )
                if already_applied:
                    print(f"✓ {filename} already applied")
                    continue

                sql = path.read_text(encoding="utf-8")
                for statement in migration_statements(sql):
                    await connection.execute(text(statement))

                await connection.execute(
                    text(
                        "INSERT INTO public.serm_schema_migrations(version) "
                        "VALUES (:version)"
                    ),
                    {"version": version},
                )
                print(f"✓ Applied {filename}")

        tenant_password = os.getenv("APP_TENANT_PASSWORD")
        if tenant_password:
            async with engine.begin() as connection:
                password_command = await connection.scalar(
                    text(
                        "SELECT format('ALTER ROLE app_tenant PASSWORD %L', CAST(:password AS text))"
                    ),
                    {"password": tenant_password},
                )
                await connection.exec_driver_sql(password_command)

        print("Database migrations are up to date.")
    except Exception:
        print(
            "Database migration failed. The current migration was rolled back; "
            "fix the reported error before retrying.",
            file=sys.stderr,
        )
        raise
    finally:
        await engine.dispose()


def main() -> None:
    load_dotenv(ROOT / ".env", override=False)
    asyncio.run(apply_migrations())


if __name__ == "__main__":
    main()
