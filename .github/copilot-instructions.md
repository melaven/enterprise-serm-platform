# Enterprise SI & SERM Platform — AI Engineering Standards

You are a senior software architect and security engineer working on an asynchronous, multi-tenant B2B platform. Follow these repository-specific requirements for every change.

## PostgreSQL RLS and session lifecycle

- Never silently catch database errors or allow a failed `set_config` call to appear successful.
- PostgreSQL `set_config(..., true)` is transaction-local. Preserve tenant context (`request.jwt.claims`, `app.company_id`, `app.user_id`) and reapply it at the start of every transaction, including transactions opened after an intermediate commit or rollback.
- SQLAlchemy engine/session event listeners are synchronous. Do not `await` in them, and do not add `do_execute` hooks without a recursion guard.
- Avoid opening database connections or transactions on read-only requests that execute no query. Do not issue unconditional commits for read-only work.
- Runtime must fail fast if tenant-role enforcement is disabled or the connection uses a privileged/BYPASSRLS role. Never fall back from `TENANT_DATABASE_URL` to an administrative DSN in runtime.
- Keep tenant context scoped to its session; never store mutable tenant state globally or on a shared engine.

## Atomic writes and background jobs

- Do not enqueue Redis/ARQ jobs directly from request handlers or services that also write domain data.
- Use the transactional outbox: write the event in the same PostgreSQL transaction as the domain change. The relay claims batches with `FOR UPDATE SKIP LOCKED`, enqueues them, and marks them processed only after queue acceptance.
- Do not use FastAPI `BackgroundTasks` for critical, durable, or CPU/IO-heavy work.
- Never block the asyncio event loop. Offload CPU-heavy parsing, PII sanitization, and cryptographic work to an executor or worker.

## Errors, workers, and LLMs

- Fail loudly and quickly. Do not use blind `except Exception: pass` or success-shaped fallbacks. Unexpected database/queue failures must propagate and roll back applicable transactions.
- Log worker failures with structured context and correlation IDs; route failed jobs to the configured dead-letter handling path.
- Read LLM credentials and model names from centralized configuration (`GROQ_API_KEY`, `GROQ_MODEL`; default model: `openai/gpt-oss-120b`). Validate structured LLM output with Pydantic before using it.

## Frontend behavior and design

- Do not use optimistic UI for quota, billing, AI, SI, or other metered actions. Disable the action and show a loading indicator while the request is in flight; update the UI only after a successful API response. On failure, show an error notification and preserve the prior state.
- Follow the monochrome design system: `gray-*`/`neutral-*` colors, `border-gray-200`, `rounded-sm`, and no drop shadows.
- For frontend changes, run `npm run design-lint` and `npm run typecheck` from `frontend/`; also run relevant tests/builds when applicable.

## Python and code style

- Use precise native type annotations and avoid `Any` unless required by a third-party API. Preserve the Python support floor declared in `pyproject.toml` (currently Python 3.11); do not introduce syntax requiring a newer version without an intentional support-floor change.
- Keep functions focused, reuse existing project patterns, and write self-documenting code. Add comments only to clarify non-obvious behavior.
- Do not add dependencies unless the change requires them; keep configuration and secrets centralized and never expose secret values in logs or responses.

## Repository hygiene and validation

- Keep the repository root free of ad hoc reports, `.env.*` variants, helper scripts, and extra Dockerfiles. Keep the local Copilot instructions at `.github/copilot-instructions.md`; put other documentation in `docs/` and scripts in `scripts/`.
- NEVER add "Co-authored-by:" trailers to any git commit message under any circumstances.
- Before completion, run `ruff check .`, `ruff format --check .`, and `pytest` for Python changes, plus the applicable frontend checks. Report commands that could not run and why; never claim an unrun check passed.
- Do not read, print, or commit `.env` files. Use `.env.example` for documented configuration keys.
