"""
Скрипт для запуска миграций базы данных
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.append(str(Path(__file__).parent.parent))

from database import engine
from migrations.add_external_review_id import upgrade_database


async def main():
    """Запуск миграции"""
    try:
        print("🚀 Запуск миграции базы данных...")
        await upgrade_database(engine)
        print("✅ Миграция завершена успешно")
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())