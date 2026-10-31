# Stripe Billing: Integration Guide

## 1. Database

```bash
python scripts/migrate.py                                # applies 013 after 012
psql "$ADMIN_DSN" -c "ALTER ROLE billing_service LOGIN PASSWORD '<secret>' CONNECTION LIMIT 5"
```

Pro plan limits in `public.plans` are placeholders (10000 reviews / 2M LLM tokens) — adjust as needed. If FORCE RLS is enabled on `tenant_quotas` (012b), SECURITY DEFINER functions from 008/013 won't write: check `\d+ tenant_quotas`.

## 2. Application

- `pyproject.toml`: `stripe` (requires version with `Session.create_async`; pin version and API version in Dashboard).
- `.env`: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (whsec_… specifically from THIS endpoint), `STRIPE_PRICE_PRO`, `BILLING_DATABASE_URL` (billing_service role), `APP_BASE_URL`.
- `main.py`: `include_router(stripe_webhook.router, prefix="/api/v1")`, `include_router(billing.router, prefix="/api/v1")`.
- Exclude webhook from global `require_csrf` and cookie-auth (it has no session; protection is signature-based). Nginx: soft `limit_req` for `/api/v1/webhooks/` (Stripe sends in batches), `client_max_body_size 1m` already exists.

## 3. Stripe Dashboard

Webhook endpoint `https://<domain>/api/v1/webhooks/stripe`, events: `checkout.session.completed`, `invoice.payment_succeeded`, `customer.subscription.deleted`.

Recommended to add `invoice.payment_failed` (past_due/notification): currently unsuccessful payments before Stripe subscription deletion are not processed.

## 4. Testing

### Local webhook testing (Stripe CLI)
```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
# Obtain webhook secret from output: whsec_...
# Set in .env: STRIPE_WEBHOOK_SECRET=whsec_...

# Trigger test event
stripe trigger checkout.session.completed
```

### Test checkout flow
```bash
# 1. Create user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123","company_name":"Test Corp"}'

# 2. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'
# Save access_token from response

# 3. Create checkout session
curl -X POST http://localhost:8000/api/v1/billing/create-checkout-session \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json"
# Open url from response in browser

# 4. Use Stripe test card: 4242 4242 4242 4242, any future date, any CVC
```

### Verify webhook processing
```bash
# Check organization status
curl http://localhost:8000/api/v1/billing/status \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Expected response after successful payment:
# {
#   "plan": "pro",
#   "status": "active",
#   "current_period_end": "2024-02-01T00:00:00Z",
#   "reviews_used": 0,
#   "reviews_limit": 10000,
#   "llm_tokens_used": 0,
#   "llm_tokens_limit": 2000000
# }
```

## 5. Production Checklist

- [ ] Set production Stripe API keys in `.env`
- [ ] Configure webhook endpoint in Stripe Dashboard
- [ ] Test webhook signature validation
- [ ] Set appropriate `STRIPE_PRICE_PRO` (production price ID)
- [ ] Configure `APP_BASE_URL` for production domain
- [ ] Set up monitoring for failed payments
- [ ] Configure customer email notifications
- [ ] Test subscription cancellation flow
- [ ] Set up billing alerts and notifications
- [ ] Document customer support procedures

## 6. Security Considerations

**Webhook Security**:
- Always validate webhook signatures
- Use HTTPS in production
- Keep webhook secret secure (never commit to git)
- Rate limit webhook endpoint
- Log all webhook events for audit

**Payment Flow**:
- Never store card details in your database
- Use Stripe-hosted checkout page
- Validate all payment amounts server-side
- Implement idempotency for payment operations
- Handle duplicate webhook deliveries

**User Data**:
- Store minimal Stripe customer metadata
- Don't expose Stripe IDs in frontend
- Implement proper access control for billing endpoints
- Audit all billing-related actions

## 7. Troubleshooting

### Webhook not received
1. Check Stripe Dashboard > Developers > Webhooks > Logs
2. Verify endpoint URL is correct and accessible
3. Check webhook secret matches `.env`
4. Review application logs for errors

### Payment succeeded but status not updated
1. Check webhook event processing in logs
2. Verify database user has write permissions
3. Check RLS policies on affected tables
4. Review transaction rollbacks in logs

### Quota not updated after payment
1. Verify `checkout.session.completed` webhook received
2. Check `tenant_quotas` table for organization
3. Review `billing_service` role permissions
4. Check for errors in `update_quota_on_subscription` function

### Customer portal not working
1. Verify Stripe customer ID exists for organization
2. Check `STRIPE_SECRET_KEY` is set correctly
3. Review customer portal configuration in Stripe Dashboard
4. Check application logs for API errors

## 8. Monitoring

**Key Metrics to Track**:
- Successful vs failed payments
- Webhook processing latency
- Subscription creation rate
- Churn rate
- Quota utilization
- Failed webhook deliveries

**Recommended Alerts**:
- Failed payment threshold (e.g., >5% in 24h)
- Webhook processing failures
- Quota limit approaching (e.g., >80% used)
- Subscription cancellation spike
- API error rate increase

## 9. API Reference

### Create Checkout Session
```http
POST /api/v1/billing/create-checkout-session
Authorization: Bearer {access_token}
Content-Type: application/json

Response:
{
  "url": "https://checkout.stripe.com/pay/...",
  "session_id": "cs_..."
}
```

### Get Billing Status
```http
GET /api/v1/billing/status
Authorization: Bearer {access_token}

Response:
{
  "plan": "pro",
  "status": "active",
  "current_period_end": "2024-02-01T00:00:00Z",
  "reviews_used": 150,
  "reviews_limit": 10000,
  "llm_tokens_used": 50000,
  "llm_tokens_limit": 2000000
}
```

### Create Customer Portal Session
```http
POST /api/v1/billing/create-portal-session
Authorization: Bearer {access_token}

Response:
{
  "url": "https://billing.stripe.com/p/session/..."
}
```

### Cancel Subscription
```http
POST /api/v1/billing/cancel-subscription
Authorization: Bearer {access_token}

Response:
{
  "status": "canceled",
  "message": "Subscription will be canceled at period end"
}
```

## 10. Database Schema Reference

```sql
-- Organizations table (Stripe customer tracking)
ALTER TABLE organizations ADD COLUMN stripe_customer_id TEXT UNIQUE;
ALTER TABLE organizations ADD COLUMN stripe_subscription_id TEXT UNIQUE;

-- Plans table (subscription tiers)
CREATE TABLE plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    reviews_limit INTEGER NOT NULL,
    llm_tokens_limit INTEGER NOT NULL,
    stripe_price_id TEXT
);

-- Tenant quotas (usage tracking)
CREATE TABLE tenant_quotas (
    organization_id UUID PRIMARY KEY REFERENCES organizations(id),
    plan_id UUID REFERENCES plans(id),
    reviews_used INTEGER DEFAULT 0,
    llm_tokens_used INTEGER DEFAULT 0,
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    status TEXT DEFAULT 'active'
);
```
