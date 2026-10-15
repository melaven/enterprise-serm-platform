# Database migrations

The supported local database is PostgreSQL 16 with pgvector, provided by
`pgvector/pgvector:pg16` in the root `docker-compose.yml`.

Run the versioned migration chain from the repository root:

```powershell
Copy-Item .env.example .env
# Set matching POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB,
# APP_TENANT_PASSWORD, and DATABASE_URL in .env.
docker compose up -d postgres
python scripts/migrate.py
python scripts/seed_db.py
```

`scripts/migrate.py` applies the ordered SQL chain transactionally, serializes
concurrent runners with a PostgreSQL advisory lock, and records successful
versions in `public.serm_schema_migrations`. It stops on the first error; fix
the reported migration issue before retrying.

The Docker backend entrypoint runs the same migration command before starting
the API. The seed script requires the migrated schema and will not create
tables or extensions itself.

`run_migration.py` and `run_multitenancy_migration.py` are compatibility
wrappers around the root runner. Do not execute individual SQL or legacy Python
migrations manually: doing so bypasses the migration ledger and can leave the
database in a partially upgraded state.
