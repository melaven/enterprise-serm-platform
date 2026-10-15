# Local database setup (Docker PostgreSQL)

The supported development database is PostgreSQL 16 with pgvector. Start from
the repository root in PowerShell.

1. Copy the environment template and set unique local values for
   `POSTGRES_PASSWORD` and `APP_TENANT_PASSWORD`. Keep passwords URL-safe so
   they can be used in the connection URLs.

   ```powershell
   Copy-Item .env.example .env
   ```

2. Ensure `DATABASE_URL` in `.env` uses the same database, username, and
   password as `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`.
   `TENANT_DATABASE_URL` should use the `app_tenant` role and
   `APP_TENANT_PASSWORD`.

3. Start PostgreSQL with pgvector and apply the full, ordered migration chain.
   Migration errors stop the runner; resolve them before continuing.

   ```powershell
   docker compose up -d postgres
   python scripts/migrate.py
   ```

4. Seed the demo tenant, platforms, 120 reviews, statistics, and LLM cache.
   The command is idempotent and also writes `mock_reputation_data.json`.

   ```powershell
   python scripts/seed_db.py
   ```

5. Start the complete stack. The backend entrypoint rechecks migrations before
   starting the API; the worker waits for the backend health check.

   ```powershell
   docker compose up -d --build
   docker compose ps
   ```

To run the backend/worker stack without reseeding, skip step 4. Do not apply
individual files under `migrations/` manually; `scripts/migrate.py` owns
ordering, locking, transactions, and migration history.
