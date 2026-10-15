# Изоляция воркеров (docker-compose фрагмент)
```yaml
networks:
  edge:    {}                       # nginx <-> api
  core:    { internal: true }       # api <-> postgres <-> redis (без выхода в интернет)
  scrape:  {}                       # воркеры парсеров: только egress через прокси
  spider:  {}                       # Telegram-паук: свой egress и прокси

services:
  api:
    networks: [edge, core]
    read_only: true
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    user: "10001:10001"
    tmpfs: ["/tmp"]
  parser_worker:                    # недоверенный вход: HTML из интернета
    networks: [core, scrape]
    read_only: true
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    environment: [DATABASE_URL=postgresql+asyncpg://worker_rw:***@db/app]   # НЕ service_role / owner
    mem_limit: 1g
    pids_limit: 256
  lead_spider:                      # НИКАКОГО доступа к core: ни БД, ни Redis, ни JWT-секретов
    networks: [spider]
    read_only: true
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    volumes: ["spider_data:/data"]  # SQLite + StringSession (secret mount, 0400)
    secrets: [tg_session, bot_token, llm_key]
    mem_limit: 512m
```
Правила
- `worker_rw` в Postgres: GRANT только на нужные таблицы/функции (`consume_quota`, insert reviews), без BYPASSRLS; работает через `set_config('app.current_company_id', …)` как и API.
- Секреты — Docker/Swarm secrets или SOPS; не в `.env` в репозитории, не в образе. Разные ключи LLM у паука и API (раздельные квоты и отзыв).
- Паук -> наружу только через список: Telegram DC, LLM-endpoint, api.telegram.org (egress-фильтр на хосте: iptables/ nftables по `DOCKER-USER`).
- Парсер: SSRF-защита — резолвить DNS самому, отвергать private/loopback/link-local/169.254.169.254, не следовать редиректам без повторной проверки (см. ssrf.py).
- Ответ парсера — недоверенные данные: лимит размера (≤5 МБ), таймаут, никакого `eval`/рендера HTML у нас; перед записью в БД — длины и схемы (pydantic), перед LLM — промпт-инъекции считаем нормой (инварианты уже проверяются кодом, не моделью).
