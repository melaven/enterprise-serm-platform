# Stripe billing: подключение

## 1. БД
```bash
psql "$ADMIN_DSN" -f sql/013_stripe_billing.sql          # после 008
psql "$ADMIN_DSN" -c "ALTER ROLE billing_service LOGIN PASSWORD '<секрет>' CONNECTION LIMIT 5"
```
Лимиты Pro в `public.plans` — плейсхолдеры (10000 отзывов / 2M LLM-токенов), поправь. Если на `tenant_quotas` включён FORCE RLS (012b),
SECURITY DEFINER-функции 008/013 перестанут писать: проверь `\d+ tenant_quotas`.

## 2. Приложение
- `requirements.txt`: `stripe` (нужна версия с `Session.create_async`; зафиксируй версию и API-версию в Dashboard).
- `.env`: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (whsec_… именно от ЭТОГО endpoint), `STRIPE_PRICE_PRO`, `BILLING_DATABASE_URL` (роль billing_service), `APP_BASE_URL`.
- `main.py`: `include_router(stripe_webhook.router, prefix="/api/v1")`, `include_router(billing.router, prefix="/api/v1")`.
- Вебхук исключить из глобального `require_csrf` и cookie-auth (у него нет сессии; защита — подпись). Nginx: `limit_req` для `/api/v1/webhooks/` мягкий (Stripe шлёт пачками), `client_max_body_size 1m` уже есть.

## 3. Stripe Dashboard
Webhook endpoint `https://<domain>/api/v1/webhooks/stripe`, события: `checkout.session.completed`, `invoice.payment_succeeded`, `customer.subscription.deleted`.
Рекомендуется добавить `invoice.payment_failed` (past_due/уведомление): сейчас неуспешные платежи до удаления подписки Stripe-ом не обрабатываются.

## 4. Проверка локально
```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe   # печатает whsec_ для .env
stripe trigger checkout.session.completed                          # у trigger нет вашего client_reference_id -> 'ignored' (ожидаемо)
curl -i -X POST localhost:8000/api/v1/webhooks/stripe -d '{}'      # без подписи -> 400
```
Полный сценарий: `POST /api/v1/billing/checkout` -> оплатить тестовой картой 4242… -> webhook -> `SELECT plan_code FROM subscriptions`.

## Чего НЕТ (осознанно)
Customer Portal, возвраты/споры, годовые планы, налоги, пробный период, past_due-логика.
