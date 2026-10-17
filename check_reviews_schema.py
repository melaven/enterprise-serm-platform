"""
Проверка схемы таблицы reviews
"""

import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()


async def check_schema():
    database_url = os.getenv("DATABASE_URL")
    engine = create_async_engine(database_url, echo=False)

    try:
        async with engine.begin() as conn:
            # Получаем все колонки таблицы reviews
            result = await conn.execute(
                text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'reviews'
                ORDER BY ordinal_position;
            """)
            )

            print("=" * 80)
            print("СХЕМА ТАБЛИЦЫ reviews")
            print("=" * 80)

            for row in result:
                nullable = "NULL" if row.is_nullable == "YES" else "NOT NULL"
                default = f" DEFAULT {row.column_default}" if row.column_default else ""
                print(
                    f"  {row.column_name:25} {row.data_type:20} {nullable:10}{default}"
                )

            print("\n" + "=" * 80)

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_schema())
