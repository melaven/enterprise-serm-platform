#!/bin/sh
set -e

echo "🚀 Starting SERM API backend entrypoint..."

# Функция для ожидания PostgreSQL
wait_for_postgres() {
    echo "⏳ Waiting for PostgreSQL to be ready..."

    # Извлекаем хост и порт из DATABASE_URL
    # Формат: postgresql+asyncpg://user:password@host:port/db
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')

    if [ -z "$DB_HOST" ]; then
        echo "❌ Could not extract DB host from DATABASE_URL"
        exit 1
    fi

    if [ -z "$DB_PORT" ]; then
        DB_PORT=5432
    fi

    echo "📡 Connecting to PostgreSQL at $DB_HOST:$DB_PORT"

    # Ждем доступности PostgreSQL (максимум 60 попыток по 1 секунде)
    MAX_TRIES=60
    COUNTER=0

    while [ $COUNTER -lt $MAX_TRIES ]; do
        if nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
            echo "✅ PostgreSQL is ready at $DB_HOST:$DB_PORT"
            return 0
        fi

        COUNTER=$((COUNTER + 1))
        echo "⏳ Attempt $COUNTER/$MAX_TRIES: PostgreSQL not ready yet..."
        sleep 1
    done

    echo "❌ PostgreSQL did not become ready after $MAX_TRIES attempts"
    exit 1
}

# Функция для запуска миграций
run_migrations() {
    echo "🔄 Running database migrations..."

    # Проверяем, есть ли скрипты миграций
    if [ -f "app/migrations/run_multitenancy_migration.py" ]; then
        echo "📋 Running multitenancy migrations..."
        python app/migrations/run_multitenancy_migration.py
    else
        echo "⚠️ Multitenancy migration script not found, skipping..."
    fi

    if [ -f "app/migrations/run_migration.py" ]; then
        echo "📋 Running additional migrations..."
        python app/migrations/run_migration.py
    else
        echo "⚠️ Additional migration script not found, skipping..."
    fi

    echo "✅ Database migrations completed"
}

# Функция для запуска SQL миграций
run_sql_migrations() {
    echo "🔄 Running SQL migrations..."

    MIGRATIONS_DIR="app/migrations"

    if [ ! -d "$MIGRATIONS_DIR" ]; then
        echo "⚠️ Migrations directory not found, skipping SQL migrations..."
        return 0
    fi

    # Сортируем SQL файлы по имени
    for sql_file in $(ls -1 "$MIGRATIONS_DIR"/*.sql 2>/dev/null | sort); do
        if [ -f "$sql_file" ]; then
            filename=$(basename "$sql_file")
            echo "📄 Executing SQL migration: $filename"

            # Выполняем SQL файл через psql
            # Извлекаем параметры подключения
            DB_USER=$(echo "$DATABASE_URL" | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')
            DB_PASSWORD=$(echo "$DATABASE_URL" | sed -n 's/.*:\([^@]*\)@.*/\1/p')
            DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')

            if [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ] || [ -z "$DB_NAME" ]; then
                echo "⚠️ Could not extract DB credentials, skipping SQL migration: $filename"
                continue
            fi

            PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$sql_file" || {
                echo "⚠️ SQL migration failed (may be already applied): $filename"
            }
        fi
    done

    echo "✅ SQL migrations completed"
}

# Основной поток выполнения
main() {
    # Ждем PostgreSQL
    wait_for_postgres

    # Запускаем миграции
    run_migrations

    # Запускаем uvicorn
    echo "🚀 Starting uvicorn server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
}

# Запускаем основную функцию
main
