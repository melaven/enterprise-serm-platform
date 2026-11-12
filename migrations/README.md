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

Review source text is stored only in the Fernet-encrypted
`review_analysis_payloads` table. It remains available for on-demand reply
generation and is deleted when its parent review is deleted. Configure
`ENCRYPTION_KEY` in `.env` using a Fernet key and keep it stable while encrypted
payloads exist; without it, review creation fails explicitly rather than
storing plaintext.

OAuth access and refresh tokens in `platform_integrations` are encrypted
automatically by the SQLAlchemy column type. Set `ENCRYPTION_SECRET_KEY` to a
valid Fernet key and keep it stable; while upgrading existing installations,
use the same value as the current `ENCRYPTION_KEY` so existing integration
ciphertext remains readable. No schema migration is required: the current
token columns are unbounded text/varchar columns.

Moderated reply text is stored separately in the tenant-isolated
`review_replies` table. `reviews.moderation_status` tracks the workflow while
the privacy-constrained reply fields on `reviews` remain `NULL`. Approval only
marks the reply as approved; publishing it to an external platform remains a
separate, disabled operation.

The AI response generator reads tenant-specific tone, compensation, and
support-channel settings from `companies`. Migration `045_add_tenant_ai_context`
adds these nullable fields. Migration `046_ai_response_generator_drafts`
preserves the original anti-crisis records as `anti_crisis_response_drafts`
and creates the separate `ai_response_drafts` table used by the generator.

Review analysis requests are written to `outbox_events` in the same database
transaction as the review. The ARQ worker relays pending events every five
seconds using tenant-scoped claims and `FOR UPDATE SKIP LOCKED`; transient Redis
errors roll back the claim so events remain pending for retry. Malformed or
unsupported events are marked `failed` for investigation.

`scripts/migrate.py` applies the ordered SQL chain transactionally, serializes
concurrent runners with a PostgreSQL advisory lock, and records successful
versions in `public.serm_schema_migrations`. It stops on the first error; fix
the reported migration issue before retrying.

Migration `051_review_archive.sql` adds the tenant-scoped soft-archive flag used
by the dashboard review list.

The Docker backend entrypoint runs the same migration command before starting
the API. The seed script requires the migrated schema and will not create
tables or extensions itself.

`run_migration.py` and `run_multitenancy_migration.py` are compatibility
wrappers around the root runner. Do not execute individual SQL or legacy Python
migrations manually: doing so bypasses the migration ledger and can leave the
database in a partially upgraded state.
