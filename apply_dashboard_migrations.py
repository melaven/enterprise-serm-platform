"""
Применение миграций для Dashboard API
Добавляет company_id и sentiment колонки в таблицу reviews
"""

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def apply_migrations():
    """Применить миграции 004 и 010 для Dashboard API"""

    # Загружаем .env файл
    from dotenv import load_dotenv

    load_dotenv()

    # Используем DATABASE_URL с правами postgres (не app_tenant)
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ DATABASE_URL не настроен в .env")
        return False

    print("=" * 60)
    print("ПРИМЕНЕНИЕ МИГРАЦИЙ ДЛЯ DASHBOARD API")
    print("=" * 60)

    # Создаем engine с правами на DDL
    engine = create_async_engine(database_url, echo=False)

    try:
        async with engine.begin() as conn:
            print("\n📋 Миграция 004: Добавление company_id для мультитенантности")
            print("-" * 60)

            # 1. Добавляем company_id
            await conn.execute(
                text("""
                ALTER TABLE public.reviews
                ADD COLUMN IF NOT EXISTS company_id UUID
                REFERENCES companies(id) ON DELETE CASCADE;
            """)
            )
            print("✅ Колонка company_id добавлена")

            # 2. Создаем индексы
            indexes_004 = [
                "CREATE INDEX IF NOT EXISTS ix_reviews_company_id ON reviews(company_id);",
                "CREATE INDEX IF NOT EXISTS ix_reviews_platform_company ON reviews(platform_id, company_id);",
                "CREATE INDEX IF NOT EXISTS ix_reviews_status_company ON reviews(status, company_id);",
                "CREATE INDEX IF NOT EXISTS ix_reviews_external_id ON reviews(external_review_id) WHERE external_review_id IS NOT NULL;",
                "CREATE INDEX IF NOT EXISTS ix_platforms_company_id ON platforms(company_id);",
            ]

            for idx_sql in indexes_004:
                await conn.execute(text(idx_sql))
                idx_name = (
                    idx_sql.split("ix_")[1].split(" ")[0]
                    if "ix_" in idx_sql
                    else "unknown"
                )
                print(f"✅ Индекс создан: ix_{idx_name}")

            # 3. Бэкфилл company_id
            result = await conn.execute(
                text("""
                UPDATE reviews
                SET company_id = platforms.company_id
                FROM platforms
                WHERE reviews.platform_id = platforms.id
                  AND reviews.company_id IS NULL;
            """)
            )
            print(f"✅ Обновлено {result.rowcount} записей с company_id")

            # 4. Проверяем NULL значения
            result = await conn.execute(
                text("""
                SELECT COUNT(*) FROM reviews WHERE company_id IS NULL;
            """)
            )
            null_count = result.scalar()

            if null_count > 0:
                print(f"⚠️ Внимание: {null_count} отзывов без company_id")
            else:
                print("✅ Все отзывы имеют company_id")

                # Делаем NOT NULL если все заполнены
                await conn.execute(
                    text("""
                    ALTER TABLE reviews
                    ALTER COLUMN company_id SET NOT NULL;
                """)
                )
                print("✅ Колонка company_id сделана обязательной")

            print("\n📋 Миграция 010: Добавление AI-полей (sentiment, tags, etc.)")
            print("-" * 60)

            # Добавляем AI-поля
            await conn.execute(
                text("""
                ALTER TABLE public.reviews
                  ADD COLUMN IF NOT EXISTS sentiment varchar(20),
                  ADD COLUMN IF NOT EXISTS tags jsonb NOT NULL DEFAULT '[]'::jsonb,
                  ADD COLUMN IF NOT EXISTS is_critical boolean NOT NULL DEFAULT false,
                  ADD COLUMN IF NOT EXISTS auto_reply text,
                  ADD COLUMN IF NOT EXISTS ai_pending boolean NOT NULL DEFAULT false,
                  ADD COLUMN IF NOT EXISTS ai_error text;
            """)
            )
            print(
                "✅ AI-поля добавлены: sentiment, tags, is_critical, auto_reply, ai_pending, ai_error"
            )

            # Проверяем структуру таблицы
            result = await conn.execute(
                text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'reviews'
                  AND column_name IN ('company_id', 'sentiment', 'tags', 'is_critical')
                ORDER BY column_name;
            """)
            )

            print("\n📊 Проверка структуры таблицы:")
            for row in result:
                nullable = "NULL" if row.is_nullable == "YES" else "NOT NULL"
                print(f"   - {row.column_name}: {row.data_type} ({nullable})")

        print("\n" + "=" * 60)
        print("✅ ВСЕ МИГРАЦИИ ПРИМЕНЕНЫ УСПЕШНО")
        print("=" * 60)
        print("\nСледующие шаги:")
        print("1. Перезапустите API сервер")
        print("2. Запустите: python test_dashboard_api.py")
        print("3. Проверьте что все 4 теста проходят")

        return True

    except Exception as e:
        print(f"\n❌ ОШИБКА ПРИМЕНЕНИЯ МИГРАЦИЙ: {str(e)}")
        print(f"   Тип ошибки: {type(e).__name__}")
        return False

    finally:
        await engine.dispose()


if __name__ == "__main__":
    success = asyncio.run(apply_migrations())
    exit(0 if success else 1)
