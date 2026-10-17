-- Restrict runtime updates to usage fields; changing limits requires tenant admin.

REVOKE UPDATE ON public.tenant_quotas FROM app_tenant;
REVOKE INSERT, DELETE ON public.tenant_quotas FROM app_tenant;
GRANT SELECT ON public.tenant_quotas TO app_tenant;

CREATE OR REPLACE FUNCTION public.reserve_llm_tokens(
    p_tenant_id uuid,
    p_tokens bigint
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $reserve$
BEGIN
    IF p_tenant_id IS DISTINCT FROM app.current_company_id() THEN
        RAISE EXCEPTION 'Tenant mismatch' USING ERRCODE = '42501';
    END IF;
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
SECURITY DEFINER
SET search_path = ''
AS $commit$
BEGIN
    IF p_tenant_id IS DISTINCT FROM app.current_company_id() THEN
        RAISE EXCEPTION 'Tenant mismatch' USING ERRCODE = '42501';
    END IF;
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
SECURITY DEFINER
SET search_path = ''
AS $release$
BEGIN
    IF p_tenant_id IS DISTINCT FROM app.current_company_id() THEN
        RAISE EXCEPTION 'Tenant mismatch' USING ERRCODE = '42501';
    END IF;
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
SECURITY DEFINER
SET search_path = ''
AS $consume$
BEGIN
    IF p_tenant_id IS DISTINCT FROM app.current_company_id() THEN
        RAISE EXCEPTION 'Tenant mismatch' USING ERRCODE = '42501';
    END IF;
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

CREATE OR REPLACE FUNCTION public.update_quota_limits(
    p_tenant_id uuid,
    p_actor_id uuid,
    p_max_llm_tokens bigint DEFAULT NULL,
    p_max_reviews bigint DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $update_limits$
BEGIN
    IF p_tenant_id IS DISTINCT FROM app.current_company_id()
       OR p_actor_id IS DISTINCT FROM app.current_user_id()
       OR NOT EXISTS (
           SELECT 1
           FROM public.company_members AS member
           WHERE member.company_id = p_tenant_id
             AND member.user_id = p_actor_id
             AND member.role IN ('owner', 'admin')
       )
    THEN
        RAISE EXCEPTION 'Quota limits can only be changed by a company admin'
            USING ERRCODE = '42501';
    END IF;

    IF p_max_llm_tokens IS NULL AND p_max_reviews IS NULL THEN
        RAISE EXCEPTION 'At least one quota limit must be specified'
            USING ERRCODE = '22023';
    END IF;

    IF (p_max_llm_tokens IS NOT NULL AND p_max_llm_tokens <= 0)
       OR (p_max_reviews IS NOT NULL AND p_max_reviews <= 0)
    THEN
        RAISE EXCEPTION 'Quota limits must be positive'
            USING ERRCODE = '22023';
    END IF;

    UPDATE public.tenant_quotas
    SET llm_tokens_limit = COALESCE(p_max_llm_tokens, llm_tokens_limit),
        reviews_parsed_limit = COALESCE(p_max_reviews, reviews_parsed_limit),
        updated_at = now()
    WHERE tenant_id = p_tenant_id;

    RETURN FOUND;
END
$update_limits$;

REVOKE ALL ON FUNCTION public.update_quota_limits(uuid, uuid, bigint, bigint)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.update_quota_limits(uuid, uuid, bigint, bigint)
    TO app_tenant;
