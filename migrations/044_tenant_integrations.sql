BEGIN;

CREATE TABLE IF NOT EXISTS public.tenant_integrations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL
        REFERENCES public.companies (id) ON DELETE CASCADE,
    platform varchar(50) NOT NULL,
    encrypted_credentials text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_tenant_integrations_company_platform
        UNIQUE (company_id, platform)
);

CREATE INDEX IF NOT EXISTS ix_tenant_integrations_company_id
    ON public.tenant_integrations (company_id);

ALTER TABLE public.tenant_integrations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_integrations_tenant_isolation
    ON public.tenant_integrations;
CREATE POLICY tenant_integrations_tenant_isolation
    ON public.tenant_integrations
    FOR ALL TO app_tenant
    USING (company_id = app.current_company_id())
    WITH CHECK (company_id = app.current_company_id());

GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.tenant_integrations TO app_tenant;
REVOKE ALL ON public.tenant_integrations FROM PUBLIC;

COMMIT;
