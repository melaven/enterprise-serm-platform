-- Align tenant_quotas with QuotaService while retaining the columns used by
-- entitlement and Stripe billing.

ALTER TABLE public.tenant_quotas
    ADD COLUMN IF NOT EXISTS reserved_llm_tokens bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE public.tenant_quotas
    ALTER COLUMN reserved_llm_tokens SET DEFAULT 0,
    ALTER COLUMN created_at SET DEFAULT now();

ALTER TABLE public.tenant_quotas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_quotas_isolation ON public.tenant_quotas;
CREATE POLICY tenant_quotas_isolation ON public.tenant_quotas
    FOR ALL TO app_tenant
    USING (tenant_id = app.current_company_id())
    WITH CHECK (tenant_id = app.current_company_id());

GRANT SELECT, UPDATE ON public.tenant_quotas TO app_tenant;

CREATE OR REPLACE FUNCTION public.check_quota_available(
    p_tenant_id uuid,
    p_tokens bigint,
    p_reviews bigint
)
RETURNS boolean
LANGUAGE sql
STABLE
AS $check$
    SELECT EXISTS (
        SELECT 1
        FROM public.tenant_quotas AS quota
        WHERE quota.tenant_id = p_tenant_id
          AND quota.is_active IS TRUE
          AND p_tokens >= 0
          AND p_reviews >= 0
          AND quota.llm_tokens_used + quota.reserved_llm_tokens + p_tokens
              <= quota.llm_tokens_limit
          AND quota.reviews_parsed_used + p_reviews
              <= quota.reviews_parsed_limit
    )
$check$;

CREATE OR REPLACE FUNCTION public.reserve_llm_tokens(
    p_tenant_id uuid,
    p_tokens bigint
)
RETURNS boolean
LANGUAGE plpgsql
AS $reserve$
BEGIN
    IF p_tokens < 0 THEN
        RAISE EXCEPTION 'Token reservation cannot be negative'
            USING ERRCODE = '22023';
    END IF;

    UPDATE public.tenant_quotas
    SET reserved_llm_tokens = reserved_llm_tokens + p_tokens,
        updated_at = now()
    WHERE tenant_id = p_tenant_id
      AND is_active IS TRUE
      AND llm_tokens_used + reserved_llm_tokens + p_tokens <= llm_tokens_limit;

    RETURN FOUND;
END
$reserve$;

CREATE OR REPLACE FUNCTION public.commit_llm_tokens(
    p_tenant_id uuid,
    p_reserved bigint,
    p_actual bigint
)
RETURNS void
LANGUAGE plpgsql
AS $commit$
BEGIN
    IF p_reserved < 0 OR p_actual < 0 THEN
        RAISE EXCEPTION 'Token counts cannot be negative'
            USING ERRCODE = '22023';
    END IF;

    UPDATE public.tenant_quotas
    SET llm_tokens_used = llm_tokens_used + p_actual,
        reserved_llm_tokens = GREATEST(0, reserved_llm_tokens - p_reserved),
        updated_at = now()
    WHERE tenant_id = p_tenant_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Quota not found for tenant %', p_tenant_id
            USING ERRCODE = 'P0002';
    END IF;
END
$commit$;

CREATE OR REPLACE FUNCTION public.release_llm_tokens(
    p_tenant_id uuid,
    p_tokens bigint
)
RETURNS void
LANGUAGE plpgsql
AS $release$
BEGIN
    IF p_tokens < 0 THEN
        RAISE EXCEPTION 'Token release cannot be negative'
            USING ERRCODE = '22023';
    END IF;

    UPDATE public.tenant_quotas
    SET reserved_llm_tokens = GREATEST(0, reserved_llm_tokens - p_tokens),
        updated_at = now()
    WHERE tenant_id = p_tenant_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Quota not found for tenant %', p_tenant_id
            USING ERRCODE = 'P0002';
    END IF;
END
$release$;

CREATE OR REPLACE FUNCTION public.consume_reviews(
    p_tenant_id uuid,
    p_count bigint
)
RETURNS boolean
LANGUAGE plpgsql
AS $consume$
BEGIN
    IF p_count < 0 THEN
        RAISE EXCEPTION 'Review count cannot be negative'
            USING ERRCODE = '22023';
    END IF;

    UPDATE public.tenant_quotas
    SET reviews_parsed_used = reviews_parsed_used + p_count,
        updated_at = now()
    WHERE tenant_id = p_tenant_id
      AND is_active IS TRUE
      AND reviews_parsed_used + p_count <= reviews_parsed_limit;

    RETURN FOUND;
END
$consume$;

REVOKE ALL ON FUNCTION public.check_quota_available(uuid, bigint, bigint) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.reserve_llm_tokens(uuid, bigint) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.commit_llm_tokens(uuid, bigint, bigint) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.release_llm_tokens(uuid, bigint) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.consume_reviews(uuid, bigint) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.check_quota_available(uuid, bigint, bigint) TO app_tenant;
GRANT EXECUTE ON FUNCTION public.reserve_llm_tokens(uuid, bigint) TO app_tenant;
GRANT EXECUTE ON FUNCTION public.commit_llm_tokens(uuid, bigint, bigint) TO app_tenant;
GRANT EXECUTE ON FUNCTION public.release_llm_tokens(uuid, bigint) TO app_tenant;
GRANT EXECUTE ON FUNCTION public.consume_reviews(uuid, bigint) TO app_tenant;
