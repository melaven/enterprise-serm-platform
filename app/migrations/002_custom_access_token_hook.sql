-- 002_custom_access_token_hook.sql
-- Кладёт company_id и company_role в JWT при выдаче/обновлении токена.
-- Включить: Dashboard -> Authentication -> Hooks -> Custom Access Token
--           -> Postgres function -> public.custom_access_token_hook
-- Локально (supabase/config.toml):
--   [auth.hook.custom_access_token]
--   enabled = true
--   uri = "pg-functions://postgres/public/custom_access_token_hook"
--
-- Клейм живёт до истечения access token (по умолчанию 1 ч): смена компании или
-- отзыв доступа вступают в силу после refresh.
BEGIN;

CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  claims jsonb := event -> 'claims';
  m      record;
BEGIN
  SELECT cm.company_id, cm.role
    INTO m
    FROM public.company_members cm
   WHERE cm.user_id = (event ->> 'user_id')::uuid;

  IF FOUND THEN
    claims := jsonb_set(claims, '{company_id}', to_jsonb(m.company_id::text));
    claims := jsonb_set(claims, '{company_role}', to_jsonb(m.role));
  END IF;

  RETURN jsonb_set(event, '{claims}', claims);
END;
$$;

REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook(jsonb)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.custom_access_token_hook(jsonb)
  TO supabase_auth_admin;

COMMIT;
