CREATE TABLE public.subscription_plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    monthly_price_usd double precision NOT NULL,
    included_tokens_per_month integer NOT NULL,
    overage_price_per_1k_usd double precision NOT NULL,
    is_active boolean NOT NULL DEFAULT true
);

CREATE TABLE public.tenant_subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL
        REFERENCES public.companies (id) ON DELETE CASCADE,
    plan_id uuid NOT NULL
        REFERENCES public.subscription_plans (id),
    status text NOT NULL DEFAULT 'active',
    current_period_start timestamptz NOT NULL,
    current_period_end timestamptz NOT NULL
);

CREATE INDEX ix_tenant_subscriptions_company_status
    ON public.tenant_subscriptions (company_id, status);

CREATE TABLE public.token_usage_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL
        REFERENCES public.companies (id) ON DELETE CASCADE,
    model_name text NOT NULL,
    input_tokens integer NOT NULL,
    output_tokens integer NOT NULL,
    total_cost_usd double precision NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_token_usage_logs_company_created
    ON public.token_usage_logs (company_id, created_at);

ALTER TABLE public.subscription_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.token_usage_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY subscription_plans_read
    ON public.subscription_plans
    FOR SELECT TO app_tenant
    USING (is_active);

CREATE POLICY tenant_subscriptions_tenant_read
    ON public.tenant_subscriptions
    FOR SELECT TO app_tenant
    USING (company_id = app.current_company_id());

CREATE POLICY token_usage_logs_tenant_access
    ON public.token_usage_logs
    FOR ALL TO app_tenant
    USING (company_id = app.current_company_id())
    WITH CHECK (company_id = app.current_company_id());

REVOKE ALL ON public.subscription_plans,
              public.tenant_subscriptions,
              public.token_usage_logs
    FROM PUBLIC, anon, authenticated;

GRANT SELECT ON public.subscription_plans,
                public.tenant_subscriptions
    TO app_tenant;
GRANT SELECT, INSERT ON public.token_usage_logs TO app_tenant;
