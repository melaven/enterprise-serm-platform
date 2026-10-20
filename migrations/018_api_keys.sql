CREATE TABLE public.api_keys (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL
        REFERENCES public.companies (id) ON DELETE CASCADE,
    name varchar(100) NOT NULL,
    key_hash varchar(64) NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz
);

CREATE INDEX ix_api_keys_tenant_id ON public.api_keys (tenant_id);

ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY api_keys_tenant_isolation ON public.api_keys
    FOR ALL TO app_tenant
    USING (tenant_id = app.current_company_id())
    WITH CHECK (tenant_id = app.current_company_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON public.api_keys TO app_tenant;

CREATE OR REPLACE FUNCTION public.lookup_api_key_tenant(p_key_hash text)
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT tenant_id
    FROM public.api_keys
    WHERE key_hash = p_key_hash
      AND revoked_at IS NULL
$$;

REVOKE ALL ON FUNCTION public.lookup_api_key_tenant(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lookup_api_key_tenant(text) TO app_tenant;
