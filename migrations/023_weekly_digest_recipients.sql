BEGIN;

CREATE OR REPLACE FUNCTION public.weekly_digest_recipients()
RETURNS TABLE (
    tenant_id uuid
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT id
    FROM public.companies
    WHERE notification_email IS NOT NULL
$$;

REVOKE ALL ON FUNCTION public.weekly_digest_recipients() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.weekly_digest_recipients() TO app_tenant;

COMMIT;
