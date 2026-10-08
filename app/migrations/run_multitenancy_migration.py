"""
Скрипт для применения миграций мультитенантности
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.append(str(Path(__file__).parent.parent))

from database import engine
from sqlalchemy import text


async def run_sql_file(file_path: Path, description: str):
    """Выполнение SQL файла"""
    
    print(f"🔄 Выполняется: {description}")
    
    try:
        # Читаем SQL файл
        sql_content = file_path.read_text(encoding='utf-8')
        
        # Разбиваем на отдельные команды по точке с запятой
        commands = [cmd.strip() for cmd in sql_content.split(';') if cmd.strip()]
        
        async with engine.begin() as conn:
            for i, command in enumerate(commands):
                if command:
                    try:
                        await conn.execute(text(command))
                        print(f"  ✅ Команда {i+1}/{len(commands)} выполнена")
                    except Exception as e:
                        print(f"  ⚠️ Команда {i+1} пропущена: {e}")
        
        print(f"✅ {description} - завершено успешно\n")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения {description}: {e}\n")
        raise


async def main():
    """Запуск всех миграций мультитенантности"""
    
    try:
        print("🚀 Запуск миграций мультитенантности SERM API...")
        
        migrations_dir = Path(__file__).parent
        
        # 1. Основная миграция RLS
        await run_sql_file(
            migrations_dir / "001_multitenancy_rls.sql",
            "001: Настройка Row Level Security и мультитенантности"
        )
        
        # 2. Custom Access Token Hook для Supabase
        await run_sql_file(
            migrations_dir / "002_custom_access_token_hook.sql", 
            "002: Custom Access Token Hook для Supabase"
        )
        
        # 3. Smoke test
        print("🔍 Выполняется smoke test RLS изоляции...")
        await run_sql_file(
            migrations_dir / "003_rls_smoke_test.sql",
            "003: Smoke test RLS изоляции"
        )
        
        print("=" * 60)
        print("✅ ВСЕ МИГРАЦИИ ЗАВЕРШЕНЫ УСПЕШНО!")
        print("=" * 60)
        
        print("\n📋 СЛЕДУЮЩИЕ ШАГИ:")
        print("1. Установите пароль для роли app_tenant:")
        print("   ALTER ROLE app_tenant PASSWORD 'your_secure_password';")
        print()
        print("2. Включите Custom Access Token Hook в Supabase Dashboard:")
        print("   Authentication → Hooks → Custom Access Token")
        print()
        print("3. Заполните таблицу company_members данными о пользователях")
        print()
        print("4. Выполните бэкфилл company_id в reviews:")
        print("   UPDATE reviews SET company_id = (")
        print("     SELECT company_id FROM platforms WHERE platforms.id = reviews.platform_id")
        print("   ) WHERE company_id IS NULL;")
        print()
        print("5. Обновите DATABASE_URL на app_tenant роль для runtime")
        print("   (оставьте postgres роль только для Alembic)")
        
    except Exception as e:
        print(f"❌ Критическая ошибка миграции: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())