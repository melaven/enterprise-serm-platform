# Трассировка: как найти всё про один запрос или джоб

Один `correlation_id` (заголовок `X-Correlation-ID`) связывает: запрос из браузера → логи API → задачу в ARQ-воркере → логи скрейпера и LLM. Логи в Docker — JSON, по одной записи на строку.

## 1. Где взять ID

| Откуда | Как |
|---|---|
| Фронтенд, ошибка | под сообщением «ID запроса: …» (выделяется кликом), также в тосте 429 |
| DevTools → Network | заголовок ответа `X-Correlation-ID` |
| Нет ответа (сеть/таймаут) | ID всё равно есть: фронт сам шлёт `X-Correlation-ID` (UUID) с каждым запросом |
| Только `job_id` (`parse:<tenant>:…`, `fetch_reviews:<company>:…`) | см. п. 3 |

Правила на сервере: берётся `X-Correlation-ID`, иначе `X-Request-ID`, иначе новый UUID4. Значение должно быть 8–128 символов `[A-Za-z0-9._:-]`, иначе заменяется на UUID. Ответ **всегда** содержит `X-Correlation-ID`, в том числе 500 (в теле `correlation_id`).

## 2. Логи по ID (PowerShell, Windows)

```powershell
$id = "9f1c2d3e-aaaa-4bbb-8ccc-0123456789ab"

# всё по цепочке: api + worker
docker compose logs --no-log-prefix --no-color api worker | Select-String $id

# читаемо: только нужные поля
docker compose logs --no-log-prefix --no-color api worker |
  Select-String $id | ForEach-Object { $_.Line | ConvertFrom-Json } |
  Select-Object timestamp, level, logger, event, job_id, status_code, duration_ms

# только за последние минуты и в потоке
docker compose logs --since 15m --no-log-prefix api worker | Select-String $id
docker compose logs -f --no-log-prefix api worker | Select-String $id   # live
```

Linux/macOS/WSL:
```bash
docker compose logs --no-log-prefix --no-color api worker | grep "$ID"
docker compose logs --no-log-prefix --no-color api worker | jq -R 'fromjson? | select(.correlation_id=="'$ID'")'
```

## 3. Логи по job_id

Статус-поллинг (`GET …/jobs/{id}`) — это отдельные запросы с **другими** correlation_id. Связь с постановкой — через `job_id`:

```powershell
$job = "parse:<tenant>:yandex:ab12cd34ef56ab12"
docker compose logs --no-log-prefix --no-color api worker | Select-String ([regex]::Escape($job))
```
Запись `parser.enqueued` / `parser_enqueued` содержит и `job_id`, и `correlation_id` → из неё берётся ID всей цепочки, дальше п. 2. Все логи задачи в воркере несут `job_id`, `job_try`, `task`.

## 4. Что вы увидите

```
api     request_finished  correlation_id=9f1c…  POST /api/v1/parser/start  202  12ms
api     parser.enqueued   correlation_id=9f1c…  job_id=parse:…
worker  job_started       correlation_id=9f1c…  job_id=parse:…  job_try=1  task=sync_platform_reviews
worker  sync.dedup …      correlation_id=9f1c…
worker  job_finished      correlation_id=9f1c…
```
События-маркеры: `request_finished` / `request_failed` (API), `job_started` / `job_retry` / `job_failed` / `job_finished` (воркер). Cron-задачи (`retry_pending_ai_reviews`) получают новый ID на каждый запуск.

## 5. Ограничения и подвохи

- Docker хранит логи ротацией (`json-file`, 10 МБ × 5 файлов на сервис): старое уйдёт. Для долгого поиска пишите вывод в файл: `docker compose logs --no-color api worker > logs.txt`.
- Строки самого arq («→ job_id:fn(...)») и необработанный traceback uvicorn пишутся вне контекста запроса и ID не несут; ищите их по `job_id` / по времени рядом с `request_failed`.
- Retry ARQ сохраняет тот же ID (kwargs хранятся в Redis), `job_try` растёт.
- Вызов `enqueue_job` напрямую (мимо `enqueue_traced`) теряет связь: воркер сгенерирует новый ID.

## 6. Подключение (один раз)

```python
# main.py каждого API-процесса
from app.core.tracing import install_tracing
app = FastAPI(...)
install_tracing(app)            # логи JSON + middleware + безопасный 500
app.add_middleware(CORSMiddleware, ...,   # CORS добавлять ПОСЛЕ: он должен быть самым внешним
    allow_headers=[..., "X-Correlation-ID"],            # фронт шлёт этот заголовок
    expose_headers=["Retry-After", "X-Correlation-ID"]) # иначе браузер не отдаст его в JS
```
- Воркеры: `@traced_task` на задаче и `configure_logging_from_env()` в `on_startup` (сделано в `app/worker` и `parser_worker/app/worker`).
- Постановка: `enqueue_traced(pool, "task", …)` вместо `pool.enqueue_job`.
- Переменные: `LOG_LEVEL` (INFO), `LOG_FORMAT` (`json` | `console` для локальной отладки).
- Фронтенд: `VITE_SEND_CORRELATION_ID=false`, если CORS бэкенда ещё не разрешает заголовок.
- `app/core/{correlation,logger,middleware,tracing}.py` продублированы в `parser_worker/app/core/` (это отдельный сервис со своим пакетом `app`); при правке меняйте обе копии.
