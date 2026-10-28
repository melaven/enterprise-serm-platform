# System Design: Tenable SERM

Technical interview and due diligence document. Format: goals → architecture → invariants → security → failures → tradeoffs.
Status notation: **[impl]** implemented in code, **[draft]** written but not connected/not run, **[plan]** designed.

---

## 1. Goals and Non-Functional Requirements

| Requirement | Technical Meaning |
|---|---|
| Strict tenant isolation | No request, no application error should reveal other tenants' reviews/parsing logs. Database-level protection (RLS) |
| Money and quotas don't lie | Quota not exceeded at any concurrency level; payment event applied exactly once |
| Heavy work outside request | Scraping and LLM in queue; API responds in milliseconds (`202`) |
| Resilience to external failures | Platforms, LLM and Stripe fail, return garbage and retry deliveries: system degrades but doesn't lose data |
| Diagnosability | Any request traceable from browser to worker with single ID |
| Security by default | Zero Trust: each boundary checks itself, compromise of one layer doesn't open others |

**Not goals (yet):** multiregion, own parsing cluster with IP rotation, real-time streaming analytics.

---

## 2. Architecture

```
                                     INTERNET
                                        |
                         +--------------v--------------+
                         |  Caddy / Nginx              |  TLS, HSTS, limit_req/limit_conn,
                         |  (edge)                     |  scanner blocking, SSE passthrough
                         +--------------+--------------+
                                        |
        +-------------------------------v--------------------------------+
        |  FastAPI (api)  - stateless, N replicas                        |
        |  middleware: tracing (X-Correlation-ID) -> security headers    |
        |  deps: JWT/JWKS -> AuthContext(company_id) -> tenant session   |
        |  routers: reviews | parser (402 gate + SSE) | billing         |
        |           webhooks/stripe (signature, no auth)                 |
        +---+-------------------+----------------------+-----------------+
            | RLS ctx           | enqueue(job_id)      | billing_service role
            v                   v                      v
   +----------------+   +----------------+     +-------------------------+
   | PostgreSQL     |   | Redis (ARQ)    |     | app.billing_* (DEFINER) |
   | RLS + DEFINER  |   | queue, results |     | stripe_events (PK)      |
   | functions      |   | AOF, password  |     +-------------------------+
   +-------^--------+   +-------+--------+
           |                    | dequeue
           |            +-------v-------------------------------------+
           |            |  ARQ workers (parser_worker)  - N replicas  |
           +------------+  1. reserve quota (atomic SQL)              |
             tenant     |  2. scrape (SSRF-guarded, per-hop checks)   |
             session    |  3. dedupe insert (ON CONFLICT DO NOTHING)  |
                        |  4. AI enrich (batch, bisect, breaker)      |
                        |  5. release unused quota                    |
                        |  cron: retry ai_pending (lease, SKIP LOCKED)|
                        +-------+--------------------+----------------+
                                |                    |
                         +------v------+      +------v--------+
                         | Marketplaces|      | LLM provider  |
                         | (HTTP)      |      | (OpenAI-compat)|
                         +-------------+      +---------------+

   +----------------------+      read-only      +------------------+
   | lead_spider          |<--------------------| Telegram (MTProto)|
   | prefilter->LLM->SQLite|                    +------------------+
   | no access to core DB |--> Bot API --> owner chat (manual outreach)
   +----------------------+
```

Layout principles: **stateless API** (scales with replicas), **all heavy work behind queue**, **spider and workers in separate networks** without access to each other, **single source of truth — PostgreSQL**.

---

## 3. Parsing Request Lifecycle

```
Client            API                      Redis/ARQ         Worker                 PostgreSQL
  |  POST /parser/jobs  (cookie+CSRF)         |                 |                        |
  |------------------>|                       |                 |                        |
  |                   | verify JWT (JWKS)     |                 |                        |
  |                   | tenant ctx: set_config(company_id)------------------------------->|
  |                   | enforce_reviews_quota ------------------------------------------>|  get_entitlement
  |<-- 402 + paywall data if used >= limit ---|                 |                        |
  |                   | job_id = company:platform:sha256(url)   |                        |
  |                   | enqueue_unique ------>| (dup -> None)   |                        |
  |<-- 409 if already running                 |                 |                        |
  |<-- 202 {job_id}   |                       |                 |                        |
  |                                           |--- dequeue ---->|                        |
  |  SSE stream of job status (parser.py)     |                 | reserve_quota(n) ----->|  consume_quota (atomic)
  |<== event: status queued/in_progress ======|<-- status ------| scrape + insert ------>|  ON CONFLICT DO NOTHING
  |                                           |                 | AI enrich              |
  |                                           |                 | release_quota(unused)->|
  |<== event: done {success} =================|<-- result ------|                        |
```

`X-Correlation-ID` present on every arrow: client → API → task payload → worker → JSON logs.

---

## 4. Data Model and Multitenancy **[impl]**

- Each tenant table contains `company_id`/`tenant_id` and enabled RLS.
- Request transaction starts with `set_config('app.current_tenant_id', :company, true)` (transaction-local). Policies compare row with this value.
- `company_id` comes **only** from signed JWT: Supabase custom access token hook puts it in claims; `user_metadata` not used (user can modify it themselves).
- Privileged operations (quota/plan changes) — only through `SECURITY DEFINER` functions with `search_path = ''`; application role has no direct `INSERT/UPDATE`.
- Roles: `app_tenant` (requests), `billing_service` (webhook, `app.billing_*` only), owner (migrations).

Key tables: `reviews` (neutral summary and analytics; dedup by tenant, platform, date, rating and summary), `tenant_quotas` (used/limit/reset_date), `plans`, `subscriptions`, `stripe_events`.

**Deliberate limitation:** can't call `session.commit()` inside request — next transaction loses tenant context. Use `flush()`, commit on context exit.

---

## 5. Concurrency and Idempotency **[impl]**

Main approach: **invariants expressed by atomic SQL statements and constraints, not locks.**

| Race | Protection | Why This Is Sufficient |
|---|---|---|
| Two workers deduct quota simultaneously | `UPDATE tenant_quotas SET used = used + :n WHERE used + :n <= limit RETURNING …` | Row lock and condition check in one statement; with READ COMMITTED loser rechecks condition on fresh row |
| Double-click "Start parsing" | Deterministic `job_id` (company + platform + sha256(url)) in ARQ | Second `enqueue` returns `None` → `409`; completed task with hanging result restarts correctly (`enqueue_unique`) |
| Review match on permitted analytical fields | `UNIQUE` + `ON CONFLICT DO NOTHING` by tenant, platform, date, rating and summary | No persistent source ID or author required |
| Stripe webhook redelivery | `stripe_events(event_id PRIMARY KEY)`, record and apply in **single** transaction | Concurrent duplicate waits for first commit and gets `false` — exactly-once apply |
| Event arrived out of order | `period_paid` returns `false` for unknown subscription → `500` → Stripe retries | Stripe doesn't guarantee delivery order; retry safer than guessing |
| Delayed deletion of old subscription | `billing_cancel` only fires for **current** `stripe_subscription_id` | Old event doesn't zero new Pro |
| Two workers take same `ai_pending` rows | `FOR UPDATE SKIP LOCKED` + lease with token | No waiting and double processing; failed worker loses lease on timeout |
| Quota reserved but work fails | Reserve-before-scrape, `release` excess in `finally`, `consume` with race retry | Worst case — temporarily "busy" quota until return, but no exceeding |

**Why not advisory locks.** Session-level `pg_advisory_lock` unsafe behind pooler in transaction mode (Supavisor/PgBouncer): lock tied to connection, client requests can go to different connections — lock "leaks" or doesn't release. Transaction-level (`pg_advisory_xact_lock`) works but holds connection and serializes what atomic `UPDATE` does without waiting. We use row locks that DBMS takes anyway, and unique constraints — they survive restarts, need no cleanup and are verified by test.

**Connection pool.** API: `pool_size=10, max_overflow=5, pool_timeout=10 s` — on exhaustion request quickly gets refusal, not queuing. Worker: `pool_size = max_jobs, max_overflow=0` — parallel tasks don't exceed connections.

---

## 6. Async Pipeline **[impl]**

- **ARQ** (Redis, AOF, password, no published port): `keep_result` limits result lifetime; `@traced_task` carries `correlation_id` to worker logging context.
- **Scraping:** platform adapters (Google, Yandex, 2GIS, Otzovik); HTTP layer with host allowlist check and **every redirect**.
- **AI enrichment:** batches of N reviews, strict `json_schema`; "poisonous" review isolated by **batch bisection**; **circuit breaker** stops sending on provider cascade failures; unmarked review gets `ai_pending=true`.
- **Background retry:** cron takes `ai_pending` with lease; provider failure doesn't burn review attempts (refund) and stops run; exhausted attempts closed as `gave_up:*`.
- **Queue security:** ARQ serializes arguments via pickle → Redis accessible only on internal network with password (otherwise write to queue = RCE).

---

## 7. Realtime: SSE **[impl]**

Parsing task progress delivered to browser via `text/event-stream`; native implementation in `app/routers/parser.py`.

- **Why SSE not WebSocket or polling:** one-way stream (server → client), goes over regular HTTP without protocol upgrade, browser auto-reconnects, client doesn't need repeated API requests.
- **Authorization:** HttpOnly cookie — EventSource sends cookies but can't set `Authorization`; this is one argument for cookie sessions (section 8). Task status access must be restricted to owning company (`job_id` contains `company_id`).
- **Edge:** for streams proxy disables buffering (`proxy_buffering off` in Nginx, `flush_interval -1` in Caddy) and increases read-timeout; configs in `infra/hardening/nginx/` and `infra/devops/deploy/` need alignment with actual SSE endpoint path.
- **Fallback:** client `waitForJob` (polling with abort, up to 3 transient 5xx, 10 min deadline) remains working for corporate proxies cutting streams.

**SSE scaling:** each open connection holds coroutine and Redis status checks. For thousands of concurrent streams next step — Redis Pub/Sub or Streams instead of polling status (**[plan]**).

---

## 8. Security (Zero Trust)

Model: each boundary checks independently, trust not inherited.

| Layer | Solution | Status |
|---|---|---|
| Identity | JWT (ES256 via JWKS), `aud`/`iss`/`exp` mandatory; JWKS failure → `503`, not `401` | impl (503 patch — draft) |
| Browser session | `__Host-` HttpOnly Secure cookie, `SameSite`, signed double-submit CSRF + `Origin` check; tokens unavailable to JS | draft (`infra/hardening/`) |
| Data | RLS on all tenant tables, DEFINER functions, minimal grants | impl |
| Headers | CSP (API: `default-src 'none'`), HSTS, nosniff, X-Frame-Options, COOP/CORP, `no-store` | draft |
| Edge | `limit_req` (api/auth/expensive), `limit_conn`, timeouts against slowloris, scanner blocking | draft |
| SSRF | platform host allowlist, every redirect checked, non-global IP and numeric forms blocked; DNS resolver guard and egress policy against rebinding | impl (hops) / draft (resolver) |
| Reviews | Original text analyzed in memory; only neutral summary by rating/fixed categories and analytical metrics saved to DB. Author name — generic label; external IDs and free responses not saved | impl |
| Payments | webhook signature on raw bytes, 5 min window, fail-closed without secret, separate DB role | impl |
| Containers | non-root, `read_only`, `cap_drop: ALL`, `no-new-privileges`, resource limits, separate networks | draft |
| Supply chain | Trivy gate before image publish, SBOM + provenance, cosign signature, gitleaks, pip-audit | draft |

### Threat Model (Brief)

| Actor / Vector | Attack | Countermeasure |
|---|---|---|
| Attacker with XSS | Token theft | Token in HttpOnly cookie; strict CSP; no inline scripts |
| Other tenant | Read/modify another company's data | RLS + `company_id` only from JWT; 404 instead of 403 for others' resources |
| Payment forgery | Fake webhook "paid" | Stripe signature, replay window, `CHECK pro_requires_stripe`, customer UNIQUE binding |
| Platform user | SSRF via parsing URL | Allowlist + hop checks + resolver + egress |
| Brute force/scan | Password guessing, scanners | `limit_req` auth zone, uniform error response, scanner blocking |
| Worker compromise | Lateral movement | Separate DB role without BYPASSRLS, network without spider and billing access, read-only FS |
| Prompt injection via reviews/chats | LLM decision hijacking | LLM has no tools and secrets; invariants (score, intent, is_lead) rechecked by code |

---

## 9. Billing (Stripe) **[impl]**

```
        checkout.session.completed (paid)
 FREE  -------------------------------------->  PRO (active)
  ^                                              |   ^
  |                                              |   | invoice.payment_succeeded
  |   customer.subscription.deleted              |   |  -> period, usage reset, reset_date = period_end
  +----------------------------------------------+---+
```

- Payment to company binding: `client_reference_id = company_id` from verified JWT on checkout creation; subsequent events find company **only** by `stripe_subscription_id` in DB.
- `plan -> limits`: `plans` defines limits, `tenant_quotas` — single counter, so worker reserve and billing don't diverge.
- Quota period matches Stripe billing period.
- `402` contains `plan`, `requests_used`, `max_requests`, `reset_date`, `upgrade_available` — enough data for paywall without second request.

Not implemented: Customer Portal, refunds and disputes, taxes, trial period, `invoice.payment_failed` (recommended to add).

---

## 10. Telegram Lead Spider **[draft]**

Purpose: find companies publicly requesting review/reputation help, pass to human.

```
Telegram event -> prefilter (regex: length, topic, intent, stopwords)
   -> dedupe (chat+msg, text hash 48h, author cooldown)
   -> LLM classify (JSON, temperature 0) -> invariants in code
   -> score >= 70 & public @username -> SQLite (TTL 30d) -> Bot API card
   -> owner presses [Take]/[Sent]/[Stop] -> status machine
```

- **Read-only**: doesn't join chats, doesn't message first; human sends first message (≤ 15/day), "Stop" = permanent opt-out.
- Two-stage filter saves LLM calls: regex filters bulk, model gets only candidates.
- Code applies invariants not model: review manipulation requests forcibly get `is_lead=false`.
- **Isolation:** own container/network, no core DB access; `StringSession` in secrets; separate Telegram account with 2FA; 1 account = 1 sticky proxy.
- Legal status of public data processing (152-FZ/GDPR) requires lawyer opinion before scaling; these are engineering measures, not legal advice.

---

## 11. Observability

- Structured JSON logs (structlog), `correlation_id` via `ContextVar`, pure ASGI middleware (doesn't break streaming and SSE).
- Event logs of key transitions: `parser_enqueued`, `stripe_event` (outcome), `billing_pro_activated`, `billing_downgraded_to_free`.
- Client shows "Request ID" in errors; support searches chain with single value.
- **[plan]** metrics (RED by routes, ARQ queue depth, oldest task age, pool utilization, `ai_pending` ratio), alerts on `stripe_event_failed`, spider FloodWait, 5xx growth.

---

## 12. Scaling and Bottlenecks

| Component | How It Scales | First Bottleneck | What To Do |
|---|---|---|---|
| API | horizontally (stateless) | DB connection pool (`10+5` per process) | pgbouncer/Supavisor limits, `WEB_CONCURRENCY`, read-replica for reads |
| Workers | horizontally, `max_jobs` per replica | outbound requests to platforms (rate limit/blocks), LLM quotas | per-domain throttle, priority queue, LLM batching |
| Redis | vertically, then Cluster/Sentinel | single instance = queue SPOF | managed Redis with replica; AOF already enabled |
| PostgreSQL | vertically, `reviews` partitioning by `company_id`/time | hot `tenant_quotas` row for one tenant | batch reserve (reserve n), not one-by-one |
| SSE | horizontally | Redis polling per connection | Pub/Sub instead of polling |

**Hot quota row:** atomic `UPDATE` serializes concurrent deductions for one tenant. This is deliberate tradeoff: correctness over single-company throughput; batch reserve (`reserve_reviews` takes `min(n, remaining)` in one call) reduces calls.

**Load numbers:** absent. Scenario `infra/devops/loadtest/k6-tenable.js` verifies invariants (dedup, quota, pool, isolation) at 1000 VU; results will be added after staging run. Until then we don't claim RPS/p95.

---

## 13. Failure Modes

| Failure | Behavior | Recovery |
|---|---|---|
| LLM unavailable/slow | Circuit breaker, reviews saved with `ai_pending` | Cron processes with lease |
| Platform blocks/changes markup | Adapter error, quota returned (`release`) | Alert, adapter fix; domain throttle |
| Redis unavailable | API returns error on enqueue; saved data intact | AOF; restart; queue tasks preserved |
| Worker crash mid-task | Task returns to queue (ARQ), lease expires | Idempotent writes — retry safe |
| JWKS unavailable | `503` (not `401`): client doesn't log out user | JWKS cache 10 min |
| Stripe sends duplicate/out of order | `duplicate` / `500` and retry | Idempotent event log |
| Connection pool exhausted | Fast refusal via `pool_timeout`, no cascade | Scaling/limits |
| FloodWait/spider account ban | Pause, auto-stop after repeats, alert | Warm up new account; core business unaffected |

---

## 14. Architectural Decisions (ADR, Brief)

1. **RLS instead of application filtering** — code bug doesn't become leak; cost: transaction discipline and `set_config`.
2. **Atomic SQL instead of advisory locks** — simpler, pooler-independent, testable; cost: per-tenant row serialization.
3. **ARQ instead of Celery** — native asyncio, fewer moving parts; cost: less ecosystem, pickle serialization requires closed Redis.
4. **SSE instead of WebSocket** — one-way stream, no protocol upgrade, works with cookie auth and regular proxies.
5. **Cookie sessions (BFF) instead of localStorage tokens** — XSS token theft protection; cost: CSRF protection and CORS with credentials.
6. **Separate role and DEFINER functions for billing** — webhook compromise doesn't give tenant data read.
7. **Spider as isolated read-only service with human in loop** — reduces ban risk and legal risks without sacrificing lead value.
8. **SQLite for spider** — single file, zero operations at dozens leads/day; migrate to Postgres on growth.

---

## 15. Verification Matrix

| What We Claim | Evidence | What's Missing |
|---|---|---|
| Quota not exceeded | Atomic `UPDATE` in 008; k6 check `used ≤ limit` | k6 run results |
| Webhook applied once | 5 parallel `event_id` inserts on PG16 → one `true`; logic tests | Integration test with real Stripe CLI |
| Stripe signature rejects forgery | Test on real SDK (forgery, modified body, replay) | Run in environment with `stripe` |
| Tenant isolation | RLS policies, SQL smoke test | Automated "A doesn't read B" test in CI |
| SSE works | Native implementation in `app/routers/parser.py` | Automated stream tests (status change, client disconnect) and integration test with real Redis |
| End-to-end correlation | Tests `tests/core/test_tracing.py` (API → worker) | — |

## 16. Roadmap to Production Ready

1. Connect SecurityMiddleware and cookie-auth to `main.py` (CSRF exception for Stripe webhook), if not already enabled.
2. CI: run `ruff`, `pytest`, Trivy; add inter-tenant isolation test.
3. Staging on Hetzner via Terraform; k6 run; publish numbers.
4. Metrics and alerts (queue, pool, 5xx, `stripe_event_failed`).
5. External pentest and legal PII processing review.
