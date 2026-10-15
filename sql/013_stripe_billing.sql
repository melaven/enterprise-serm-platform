-- 013_stripe_billing.sql: тарифы, подписки Stripe, идемпотентность вебхуков.
-- Требует 008 (tenant_quotas, app.current_tenant_id). Применять под postgres.
--
-- Модель доверия:
--   * арендатор может ТОЛЬКО ЧИТАТЬ свою подписку и список тарифов;
--   * менять план/лимиты может только роль billing_service через SECURITY DEFINER функции app.billing_*
--     (её DSN используется только вебхук-обработчиком; app_tenant выполнять эти функции НЕ может);
--   * источник истины об оплате — подписанное событие Stripe, не клиент и не JWT.
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.tenant_quotas') IS NULL THEN
    RAISE EXCEPTION 'apply 008_billing_quotas.sql first';
  END IF;
END $$;

-- ---------- роль вебхука (логин и пароль выдаются вне миграции) ----------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'billing_service') THEN
    CREATE ROLE billing_service NOLOGIN;
  END IF;
END $$;
-- Затем вне git:  ALTER ROLE billing_service LOGIN PASSWORD '<из секрет-хранилища>' CONNECTION LIMIT 5;
GRANT USAGE ON SCHEMA app TO billing_service;

-- ---------- тарифы ----------
CREATE TABLE IF NOT EXISTS public.plans (
  code                 text PRIMARY KEY CHECK (code IN ('free', 'pro')),
  name                 text   NOT NULL,
  reviews_parsed_limit bigint NOT NULL CHECK (reviews_parsed_limit >= 0),
  llm_tokens_limit     bigint NOT NULL CHECK (llm_tokens_limit >= 0)
);
-- Лимиты Pro — ПЛЕЙСХОЛДЕРЫ: поставь свои. Free = текущие дефолты 008.
INSERT INTO public.plans (code, name, reviews_parsed_limit, llm_tokens_limit) VALUES
  ('free', 'Free', 500,   100000),
  ('pro',  'Pro',  10000, 2000000)
ON CONFLICT (code) DO NOTHING;

-- ---------- подписки ----------
CREATE TABLE IF NOT EXISTS public.subscriptions (
  tenant_id              uuid PRIMARY KEY REFERENCES public.companies (id) ON DELETE CASCADE,
  plan_code              text NOT NULL DEFAULT 'free' REFERENCES public.plans (code),
  status                 text NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active', 'past_due', 'canceled')),
  stripe_customer_id     text UNIQUE,
  stripe_subscription_id text UNIQUE,
  current_period_start   timestamptz,
  current_period_end     timestamptz,
  canceled_at            timestamptz,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  -- платный план без Stripe-подписки невозможен: нельзя «выдать Pro руками» обычным UPDATE
  CONSTRAINT pro_requires_stripe CHECK (plan_code = 'free' OR stripe_subscription_id IS NOT NULL)
);

CREATE OR REPLACE FUNCTION app.create_default_subscription()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.subscriptions (tenant_id) VALUES (NEW.id) ON CONFLICT (tenant_id) DO NOTHING;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS companies_default_subscription ON public.companies;
CREATE TRIGGER companies_default_subscription
  AFTER INSERT ON public.companies
  FOR EACH ROW EXECUTE FUNCTION app.create_default_subscription();

INSERT INTO public.subscriptions (tenant_id)
SELECT id FROM public.companies ON CONFLICT (tenant_id) DO NOTHING;

-- ---------- журнал событий Stripe (идемпотентность) ----------
CREATE TABLE IF NOT EXISTS public.stripe_events (
  event_id    text PRIMARY KEY,                 -- evt_...
  type        text NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now()
);

-- ---------- RLS / права ----------
ALTER TABLE public.plans          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stripe_events  ENABLE ROW LEVEL SECURITY;   -- без политик: никому, кроме владельца/definer

DO $$
DECLARE roles text;
BEGIN
  SELECT string_agg(quote_ident(rolname), ', ') INTO roles
  FROM pg_roles WHERE rolname IN ('app_tenant', 'authenticated');
  EXECUTE 'DROP POLICY IF EXISTS tenant_select ON public.subscriptions';
  EXECUTE format('CREATE POLICY tenant_select ON public.subscriptions FOR SELECT TO %s '
                 'USING (tenant_id = (SELECT app.current_tenant_id()))', roles);
  EXECUTE 'DROP POLICY IF EXISTS plans_read ON public.plans';
  EXECUTE format('CREATE POLICY plans_read ON public.plans FOR SELECT TO %s USING (true)', roles);
END $$;

REVOKE ALL ON public.plans, public.subscriptions, public.stripe_events FROM PUBLIC, anon, authenticated;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_tenant') THEN
    REVOKE ALL ON public.plans, public.subscriptions, public.stripe_events FROM app_tenant;
    GRANT SELECT ON public.plans, public.subscriptions TO app_tenant;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    GRANT SELECT ON public.plans, public.subscriptions TO authenticated;
  END IF;
END $$;

-- ---------- чтение для роутера (под tenant-контекстом) ----------
CREATE OR REPLACE FUNCTION app.get_entitlement(p_tenant_id uuid)
RETURNS TABLE (plan_code text, status text, reviews_parsed_used bigint,
               reviews_parsed_limit bigint, reset_date date)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
  IF p_tenant_id IS DISTINCT FROM app.current_tenant_id() THEN
    RAISE EXCEPTION 'tenant mismatch' USING ERRCODE = '42501';
  END IF;
  PERFORM app.roll_quota_period(p_tenant_id);
  RETURN QUERY
  SELECT s.plan_code, s.status, q.reviews_parsed_used, q.reviews_parsed_limit, q.reset_date
  FROM public.subscriptions s JOIN public.tenant_quotas q USING (tenant_id)
  WHERE s.tenant_id = p_tenant_id;
END $$;

-- ---------- функции вебхука: ТОЛЬКО billing_service ----------
-- 1) идемпотентность: true = событие новое. Вызывать в той же транзакции, что и применение.
CREATE OR REPLACE FUNCTION app.billing_record_event(p_event_id text, p_type text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.stripe_events (event_id, type) VALUES (p_event_id, p_type)
  ON CONFLICT (event_id) DO NOTHING;
  RETURN FOUND;   -- конкурентный дубль ждёт коммита первого и получает false
END $$;

-- 2) оплата подписки (checkout.session.completed, paid) -> Pro
CREATE OR REPLACE FUNCTION app.billing_activate_pro(
  p_tenant_id uuid, p_customer text, p_subscription text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
DECLARE v_reviews bigint; v_llm bigint;
BEGIN
  SELECT reviews_parsed_limit, llm_tokens_limit INTO v_reviews, v_llm FROM public.plans WHERE code = 'pro';
  IF NOT EXISTS (SELECT 1 FROM public.companies WHERE id = p_tenant_id) THEN
    RAISE EXCEPTION 'unknown tenant %', p_tenant_id USING ERRCODE = 'P0002';
  END IF;

  INSERT INTO public.subscriptions AS s (tenant_id, plan_code, status, stripe_customer_id, stripe_subscription_id)
  VALUES (p_tenant_id, 'pro', 'active', p_customer, p_subscription)
  ON CONFLICT (tenant_id) DO UPDATE
    SET plan_code = 'pro', status = 'active',
        -- customer уже привязан к другому tenant -> нарушение UNIQUE -> 500 -> алерт (атака/ошибка маппинга)
        stripe_customer_id = EXCLUDED.stripe_customer_id,
        stripe_subscription_id = EXCLUDED.stripe_subscription_id,
        canceled_at = NULL, updated_at = now();

  UPDATE public.tenant_quotas
     SET reviews_parsed_limit = v_reviews, llm_tokens_limit = v_llm, updated_at = now()
   WHERE tenant_id = p_tenant_id;
END $$;

-- 3) успешный платёж периода (invoice.payment_succeeded): продлить период, сбросить счётчики.
--    false = подписка ещё неизвестна (событие пришло раньше checkout.*): вызывающий отвечает 500, Stripe повторит.
CREATE OR REPLACE FUNCTION app.billing_period_paid(
  p_subscription text, p_period_start timestamptz, p_period_end timestamptz, p_reset_usage boolean)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
DECLARE v_tenant uuid;
BEGIN
  UPDATE public.subscriptions
     SET status = 'active',
         current_period_start = COALESCE(p_period_start, current_period_start),
         current_period_end   = COALESCE(p_period_end, current_period_end),
         updated_at = now()
   WHERE stripe_subscription_id = p_subscription AND plan_code = 'pro'
   RETURNING tenant_id INTO v_tenant;
  IF v_tenant IS NULL THEN RETURN false; END IF;

  UPDATE public.tenant_quotas
     SET reviews_parsed_used = CASE WHEN p_reset_usage THEN 0 ELSE reviews_parsed_used END,
         llm_tokens_used     = CASE WHEN p_reset_usage THEN 0 ELSE llm_tokens_used END,
         reset_date = COALESCE((p_period_end AT TIME ZONE 'UTC')::date, reset_date),  -- период квоты = период оплаты
         updated_at = now()
   WHERE tenant_id = v_tenant;
  RETURN true;
END $$;

-- 4) подписка удалена (customer.subscription.deleted) -> Free.
--    Только если удалена ТЕКУЩАЯ подписка: запоздавшее событие старой подписки не должно ронять новый Pro.
CREATE OR REPLACE FUNCTION app.billing_cancel(p_subscription text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = ''
AS $$
DECLARE v_tenant uuid; v_reviews bigint; v_llm bigint;
BEGIN
  SELECT reviews_parsed_limit, llm_tokens_limit INTO v_reviews, v_llm FROM public.plans WHERE code = 'free';
  UPDATE public.subscriptions
     SET plan_code = 'free', status = 'canceled', canceled_at = now(), updated_at = now()
   WHERE stripe_subscription_id = p_subscription
   RETURNING tenant_id INTO v_tenant;
  IF v_tenant IS NULL THEN RETURN false; END IF;

  UPDATE public.tenant_quotas
     SET reviews_parsed_limit = v_reviews, llm_tokens_limit = v_llm, updated_at = now()
   WHERE tenant_id = v_tenant;   -- used не трогаем: сброс по reset_date
  RETURN true;
END $$;

REVOKE ALL ON FUNCTION
  app.create_default_subscription(), app.get_entitlement(uuid),
  app.billing_record_event(text, text), app.billing_activate_pro(uuid, text, text),
  app.billing_period_paid(text, timestamptz, timestamptz, boolean), app.billing_cancel(text)
FROM PUBLIC;

GRANT EXECUTE ON FUNCTION
  app.billing_record_event(text, text), app.billing_activate_pro(uuid, text, text),
  app.billing_period_paid(text, timestamptz, timestamptz, boolean), app.billing_cancel(text)
TO billing_service;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_tenant') THEN
    GRANT EXECUTE ON FUNCTION app.get_entitlement(uuid) TO app_tenant;
  END IF;
END $$;

COMMIT;
