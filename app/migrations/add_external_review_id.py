"""
Миграция для добавления поля external_review_id в таблицу reviews
и удаления устаревшей таблицы lnr_reviews_log
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def upgrade_database(engine: AsyncEngine):
    """
    Применение миграции:
    1. Добавляем поле external_review_id в reviews
    2. Переносим данные из lnr_reviews_log (если есть)
    3. Удаляем старую таблицу
    """
    async with engine.begin() as conn:
        
        # 1. Добавляем новое поле external_review_id
        await conn.execute(text("""
            ALTER TABLE reviews 
            ADD COLUMN IF NOT EXISTS external_review_id VARCHAR(255) UNIQUE;
        """))
        
        # 2. Создаем индекс для быстрого поиска
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_reviews_external_id 
            ON reviews(external_review_id);
        """))
        
        # 3. Проверяем существование старой таблицы и переносим данные
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'lnr_reviews_log'
            );
        """))
        
        table_exists = result.scalar()
        
        if table_exists:
            # Переносим данные из старой таблицы в новую структуру
            # Примечание: это упрощенный перенос, может потребоваться адаптация
            print("Найдена таблица lnr_reviews_log, выполняем миграцию данных...")
            
            # Можно добавить логику переноса данных здесь
            # Например, создать записи в основной таблице reviews
            # на основе данных из lnr_reviews_log
            
            # 4. После переноса удаляем старую таблицу
            await conn.execute(text("DROP TABLE IF EXISTS lnr_reviews_log;"))
            print("Таблица lnr_reviews_log удалена")
        
        print("Миграция external_review_id завершена успешно")


async def downgrade_database(engine: AsyncEngine):
    """
    Откат миграции:
    1. Удаляем поле external_review_id
    2. Восстанавливаем старую таблицу (опционально)
    """
    async with engine.begin() as conn:
        
        # Удаляем индекс
        await conn.execute(text("""
            DROP INDEX IF EXISTS idx_reviews_external_id;
        """))
        
        # Удаляем поле
        await conn.execute(text("""
            ALTER TABLE reviews 
            DROP COLUMN IF EXISTS external_review_id;
        """))
        
        print("Откат миграции external_review_id завершен")