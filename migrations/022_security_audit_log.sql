BEGIN;

CREATE TABLE IF NOT EXISTS public.audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL
        REFERENCES public.companies (id) ON DELETE CASCADE,
    user_id uuid,
    action varchar(100) NOT NULL,
    ip_address varchar(45),
    timestamp timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_tenant_timestamp
    ON public.audit_logs (tenant_id, timestamp DESC);

ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'audit_logs'
          AND policyname = 'audit_logs_tenant_isolation'
    ) THEN
        CREATE POLICY audit_logs_tenant_isolation
            ON public.audit_logs
            FOR ALL TO app_tenant
            USING (tenant_id = app.current_company_id())
            WITH CHECK (tenant_id = app.current_company_id());
    END IF;
END
$$;

GRANT SELECT, INSERT ON public.audit_logs TO app_tenant;

COMMIT;
