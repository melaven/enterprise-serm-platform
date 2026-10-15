"""
Миграция для обновления моделей под мультитенантность
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def upgrade_models_for_multitenancy(engine: AsyncEngine):
    """
    Обновление моделей для мультитенантности:
    1. Добавление company_id в reviews (если не добавлено)
    2. Создание индексов для производительности
    3. Обновление внешних ключей
    4. Бэкфилл данных
    """
    async with engine.begin() as conn:
        
        print("🔄 Обновление моделей для мультитенантности...")
        
        # 1. Добавляем company_id в reviews (если не существует)
        await conn.execute(text("""
            ALTER TABLE reviews 
            ADD COLUMN IF NOT EXISTS company_id UUID 
            REFERENCES companies(id) ON DELETE CASCADE;
        """))
        print("✅ Поле company_id добавлено в reviews")
        
        # 2. Создаем индексы для производительности RLS
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_reviews_company_id ON reviews(company_id);",
            "CREATE INDEX IF NOT EXISTS ix_reviews_platform_company ON reviews(platform_id, company_id);",
            "CREATE INDEX IF NOT EXISTS ix_reviews_status_company ON reviews(status, company_id);",
            "CREATE INDEX IF NOT EXISTS ix_reviews_external_id ON reviews(external_review_id) WHERE external_review_id IS NOT NULL;",
            "CREATE INDEX IF NOT EXISTS ix_platforms_company_id ON platforms(company_id);",
        ]
        
        for index_sql in indexes:
            try:
                await conn.execute(text(index_sql))
                print(f"✅ Индекс создан: {index_sql.split('ix_')[1].split(' ')[0]}")
            except Exception as e:
                print(f"⚠️ Индекс пропущен: {e}")
        
        # 3. Выполняем бэкфилл company_id в reviews
        result = await conn.execute(text("""
            UPDATE reviews 
            SET company_id = platforms.company_id
            FROM platforms 
            WHERE reviews.platform_id = platforms.id 
              AND reviews.company_id IS NULL;
        """))
        
        updated_rows = result.rowcount
        print(f"✅ Обновлено {updated_rows} записей в reviews с company_id")
        
        # 4. Проверяем что все reviews имеют company_id
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM reviews WHERE company_id IS NULL;
        """))
        
        null_company_count = result.scalar()
        if null_company_count > 0:
            print(f"⚠️ Внимание: {null_company_count} отзывов без company_id")
        else:
            print("✅ Все отзывы имеют company_id")
        
        # 5. Делаем company_id обязательным (NOT NULL)
        if null_company_count == 0:
            await conn.execute(text("""
                ALTER TABLE reviews 
                ALTER COLUMN company_id SET NOT NULL;
            """))
            print("✅ Поле company_id сделано обязательным")
        
        print("✅ Модели обновлены для мультитенантности")


async def downgrade_models_multitenancy(engine: AsyncEngine):
    """Откат изменений моделей"""
    async with engine.begin() as conn:
        
        print("🔄 Откат изменений мультитенантности...")
        
        # Убираем ограничение NOT NULL
        await conn.execute(text("""
            ALTER TABLE reviews 
            ALTER COLUMN company_id DROP NOT NULL;
        """))
        
        # Удаляем индексы
        indexes_to_drop = [
            "DROP INDEX IF EXISTS ix_reviews_company_id;",
            "DROP INDEX IF EXISTS ix_reviews_platform_company;", 
            "DROP INDEX IF EXISTS ix_reviews_status_company;",
            "DROP INDEX IF EXISTS ix_platforms_company_id;",
        ]
        
        for drop_sql in indexes_to_drop:
            try:
                await conn.execute(text(drop_sql))
            except Exception as e:
                print(f"⚠️ Ошибка удаления индекса: {e}")
        
        # Можем оставить company_id колонку, но обнулить значения
        # await conn.execute(text("UPDATE reviews SET company_id = NULL;"))
        
        print("✅ Откат изменений моделей завершен")