-- Repair entitlement functions for databases that already applied migration 013.

CREATE OR REPLACE FUNCTION app.roll_quota_period(p_tenant_id uuid)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
    UPDATE public.tenant_quotas
    SET reviews_parsed_used = 0,
        llm_tokens_used = 0,
        reset_date = now() + interval '30 days',
        updated_at = now()
    WHERE tenant_id = p_tenant_id
      AND reset_date <= now()
$$;

REVOKE ALL ON FUNCTION app.roll_quota_period(uuid) FROM PUBLIC;

CREATE OR REPLACE FUNCTION app.get_entitlement(p_tenant_id uuid)
RETURNS TABLE (plan_code text, status text, reviews_parsed_used bigint,
               reviews_parsed_limit bigint, reset_date date)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  IF p_tenant_id IS DISTINCT FROM app.current_company_id() THEN
    RAISE EXCEPTION 'tenant mismatch' USING ERRCODE = '42501';
  END IF;

  PERFORM app.roll_quota_period(p_tenant_id);

  RETURN QUERY
  SELECT subscription.plan_code, subscription.status,
         quota.reviews_parsed_used, quota.reviews_parsed_limit, quota.reset_date
  FROM public.subscriptions AS subscription
  JOIN public.tenant_quotas AS quota USING (tenant_id)
  WHERE subscription.tenant_id = p_tenant_id;
END
$$;

REVOKE ALL ON FUNCTION app.get_entitlement(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.get_entitlement(uuid) TO app_tenant;
