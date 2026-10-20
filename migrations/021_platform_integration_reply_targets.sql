BEGIN;

CREATE TABLE IF NOT EXISTS public.platform_integrations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL
        REFERENCES public.companies (id) ON DELETE CASCADE,
    platform varchar(50) NOT NULL,
    encrypted_api_key text NOT NULL,
    external_account_id varchar(255),
    external_location_id varchar(255),
    is_active boolean NOT NULL DEFAULT true,
    last_synced_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_platform_integrations_company_platform
        UNIQUE (company_id, platform)
);

ALTER TABLE public.platform_integrations
    ADD COLUMN IF NOT EXISTS external_account_id varchar(255),
    ADD COLUMN IF NOT EXISTS external_location_id varchar(255);

CREATE INDEX IF NOT EXISTS ix_platform_integrations_company_id
    ON public.platform_integrations (company_id);

ALTER TABLE public.platform_integrations ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'platform_integrations'
          AND policyname = 'platform_integrations_tenant_isolation'
    ) THEN
        CREATE POLICY platform_integrations_tenant_isolation
            ON public.platform_integrations
            FOR ALL TO app_tenant
            USING (company_id = app.current_company_id())
            WITH CHECK (company_id = app.current_company_id());
    END IF;
END
$$;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.platform_integrations TO app_tenant;

COMMIT;
