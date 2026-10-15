# Tenable — Zero Trust Hardening (приоритизированный чеклист)

Файлы: `app_core/` (security_headers, cookie_auth, pii, ssrf, security_patch.md), `nginx/tenable.conf`, `ops/` (isolation.md, opsec_parsers.py).
Статус проверки: pure-Python части (`pii`, `ssrf`, `opsec_parsers`) прогнаны; `security_headers`/`cookie_auth` и nginx-конфиг **не запускались** (нет fastapi/nginx в песочнице) — прогнать `nginx -t` и интеграционный тест до выката.

## CRITICAL (блокируют релиз)
- [ ] **C1. JWT только в HttpOnly-cookie** → `cookie_auth.py` + правки `security_patch.md`. Вектор: XSS → кража токена из localStorage/Zustand-persist. Убрать `Authorization` из `client.ts`, `withCredentials: true`, `partialize` без токенов.
- [ ] **C2. CSRF** (обязательно вместе с C1): `__Host-` cookie, SameSite, double-submit HMAC + проверка `Origin`. Без этого переход на cookie *ухудшает* безопасность.
- [ ] **C3. CORS**: явный список origin, `allow_credentials=True` только с ним, никогда `*`.
- [ ] **C4. SSRF в парсерах** → `ssrf.py`: https-only, публичные IP, pin IP, повторная проверка на каждом редиректе. Вектор: пользователь передаёт `url` в `/parser/start` → доступ к metadata/внутренним сервисам.
- [ ] **C5. Воркеры без привилегий**: отдельная роль БД (`worker_rw`, без BYPASSRLS/service_role), паук без доступа к core-сети (`ops/isolation.md`). Вектор: RCE/инъекция через недоверенный HTML → полный доступ к данным всех tenant'ов.
- [ ] **C6. Секреты**: `StringSession`, bot token, LLM-ключи, `csrf_secret`, pepper — только secrets-хранилище; ротация при любом подозрении; Telegram-аккаунт отдельный, 2FA.
- [ ] **C7. JWKS-сбой → 503, не 401** и без fallback на неподписанные токены (`security_patch.md`).
- [ ] **C8. `/docs`, `/openapi.json` выключены в prod** (nginx 404 + `docs_url=None`).

## HIGH
- [ ] **H1. SecurityMiddleware** (`security_headers.py`): CSP `default-src 'none'` для API, HSTS, nosniff, X-Frame-Options, COOP/CORP, `Cache-Control: no-store`. SPA-CSP — в nginx (`script-src 'self'`).
- [ ] **H2. Nginx L7** (`tenable.conf`): `limit_req` (api/auth/expensive), `limit_conn`, таймауты против slowloris, блок сканеров по UA/пути (444), `real_ip` только от доверенного LB. UA-фильтр — шумоподавление; от целевых атак нужен WAF/Cloudflare.
- [ ] **H3. PII-стратегия** (`pii.py`): HMAC-SHA256+pepper (версии ключа) для username/авторов, сырые значения — TTL 30 дней (`PURGE_SQL`, ARQ cron раз в сутки), `suppression_list` только из хешей (opt-out «Стоп»). Логи парсинга — TTL 7–14 дней. Миграция — `MIGRATION_SQL`.
- [ ] **H4. Rate limit на уровне приложения** (Redis, per-user + per-company) под nginx: защита от обхода по IP-пулу и от расхода платной квоты.
- [ ] **H5. Brute-force/enumeration**: единый ответ `Invalid credentials`, lockout/captcha после N попыток (Supabase Auth rate limits + `auth` zone).
- [ ] **H6. RLS**: применить FORCE RLS на всех tenant-таблицах, тест «tenant A не читает B» в CI.
- [ ] **H7. Контейнеры**: non-root, `read_only`, `cap_drop: ALL`, `no-new-privileges`, лимиты mem/pids, egress-allowlist для паука.
- [ ] **H8. Prompt injection**: текст чатов/отзывов — недоверенный; решения (is_lead, intent) валидируются кодом (уже в `parse_classification`); LLM не имеет tool-доступа и не видит секретов.
- [ ] **H9. Зависимости**: `pip-audit`/`npm audit` + Dependabot в CI, lock-файлы с хешами (`pip install --require-hashes`).

## MEDIUM
- [ ] **M1.** Telegram OpSec (`opsec_parsers.py`): 1 аккаунт = 1 sticky-прокси = фиксированные параметры устройства; **не** ротировать прокси внутри аккаунта (это триггер бана); ротация — между аккаунтами. Джиттер `jitter()`, `DomainThrottle` с backoff, автостоп при 2 FloodWait/сутки.
- [ ] **M2.** Парсеры: соблюдать ToS и robots площадок; per-domain throttle; 3 блокировки подряд → пауза домена на сутки + алерт. Обход капч/антибота — юридический и репутационный риск, не закладывать.
- [ ] **M3.** Аудит-лог: кто/когда/что (login, refresh, parser start, экспорт, удаление) с `correlation_id` (TRACING.md), без PII и токенов в логах (redaction-processor в structlog).
- [ ] **M4.** Бэкапы Postgres шифрованные, retention ≤ TTL PII (иначе «удалённое» живёт в бэкапах); проверка restore раз в квартал.
- [ ] **M5.** Subresource/CSP-report: `report-to` + сбор нарушений; позже nonce вместо `style 'unsafe-inline'`.
- [ ] **M6.** DSAR/удаление: эндпоинт/скрипт «удалить по username» (хеш → удалить лид, оставить запись в suppression_list).
- [ ] **M7.** Pentest/DAST (ZAP) на staging перед релизом, секрет-скан (gitleaks) в pre-commit и CI.

## Правовая оговорка
Пункты 152-ФЗ/GDPR — инженерные меры, не юридическое заключение. Для публичных данных из чатов/отзывов нужно правовое основание, уведомление, локализация данных граждан РФ (152-ФЗ ст. 18 ч. 5) — согласовать с юристом до масштабирования.

## Порядок внедрения (1 неделя)
1. День 1: C3, C7, C8, H1 (быстро, низкий риск). 2. День 2–3: C1+C2 (бэкенд+фронт вместе, один релиз). 3. День 3: C4, C5, H7. 4. День 4: H2 (staging, `nginx -t`, нагрузочный тест). 5. День 5: H3 (миграция + cron). 6. День 6–7: H4–H6, тесты, пентест.
