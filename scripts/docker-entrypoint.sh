#!/bin/sh
set -eu

database_endpoint="$(python -c "from sqlalchemy.engine import make_url; import os; url=make_url(os.environ['DATABASE_URL']); print(f'{url.host} {url.port or 5432}')")"
db_host="${database_endpoint% *}"
db_port="${database_endpoint##* }"

if [ -z "$db_host" ]; then
    echo "DATABASE_URL must contain a PostgreSQL host." >&2
    exit 1
fi

echo "Waiting for PostgreSQL at $db_host:$db_port..."
attempt=0
while ! nc -z "$db_host" "$db_port"; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 60 ]; then
        echo "PostgreSQL did not become ready after 60 seconds." >&2
        exit 1
    fi
    sleep 1
done

echo "Applying database migrations..."
python scripts/migrate.py

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
