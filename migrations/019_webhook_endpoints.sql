BEGIN;

CREATE TABLE public.webhook_endpoints (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL
        REFERENCES public.companies (id) ON DELETE CASCADE,
    url varchar(2048) NOT NULL,
    secret_key varchar(128) NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_webhook_endpoints_company_active
    ON public.webhook_endpoints (company_id, is_active);

ALTER TABLE public.webhook_endpoints ENABLE ROW LEVEL SECURITY;

CREATE POLICY webhook_endpoints_tenant_isolation
    ON public.webhook_endpoints
    FOR ALL TO app_tenant
    USING (company_id = app.current_company_id())
    WITH CHECK (company_id = app.current_company_id());

GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.webhook_endpoints TO app_tenant;

COMMIT;
