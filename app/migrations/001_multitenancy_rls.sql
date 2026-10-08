-- 001_multitenancy_rls.sql
-- Применять под миграционной ролью (postgres), НЕ под app_tenant.
-- Перед запуском: во всех таблицах из списка ниже у company_id не должно быть NULL.
BEGIN;

CREATE SCHEMA IF NOT EXISTS app;

-- 1. Runtime-роль приложения: LOGIN, без BYPASSRLS.
--    Сразу после создания: ALTER ROLE app_tenant PASSWORD '<strong-password>';
--    Строка подключения FastAPI: app_tenant.<project_ref> через Supavisor (:6543).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_tenant') THEN
    CREATE ROLE app_tenant LOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT
      PASSWORD 'CHANGE_ME';
  END IF;
END $$;

GRANT USAGE ON SCHEMA public, app TO app_tenant;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_tenant;

-- 2. Модель тенантов: один пользователь = одна компания.
CREATE TABLE IF NOT EXISTS public.companies (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.company_members (
  user_id    uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  company_id uuid NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
  role       text NOT NULL DEFAULT 'member'
             CHECK (role IN ('owner', 'admin', 'member')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS company_members_company_idx
  ON public.company_members (company_id);

-- 3. Контекст запроса. Fail-closed: GUC не задан -> NULL -> 0 строк.
--    NULLIF обязателен: после COMMIT/ROLLBACK set_config(..., true) оставляет
--    в сессии пустую строку, а не NULL.
CREATE OR REPLACE FUNCTION app.current_company_id()
RETURNS uuid
LANGUAGE sql STABLE
AS $$
  SELECT NULLIF(current_setting('app.company_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION app.current_user_id()
RETURNS uuid
LANGUAGE sql STABLE
AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
$$;

GRANT EXECUTE ON FUNCTION app.current_company_id(), app.current_user_id()
  TO app_tenant;

-- 4. RLS на бизнес-таблицах (company_id uuid должен существовать).
DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['reviews', 'financial_losses'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'ALTER TABLE public.%I ALTER COLUMN company_id SET NOT NULL', t);
    EXECUTE format(
      'ALTER TABLE public.%I ALTER COLUMN company_id '
      'SET DEFAULT app.current_company_id()', t);
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON public.%I (company_id)',
      t || '_company_id_idx', t);

    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON public.%I', t);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON public.%I '
      'FOR ALL TO app_tenant '
      'USING (company_id = app.current_company_id()) '
      'WITH CHECK (company_id = app.current_company_id())', t);

    EXECUTE format(
      'GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO app_tenant', t);
  END LOOP;
END $$;

-- 5. Справочные таблицы: только чтение в рамках своей компании.
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_members ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS own_company ON public.companies;
CREATE POLICY own_company ON public.companies
  FOR SELECT TO app_tenant
  USING (id = app.current_company_id());

DROP POLICY IF EXISTS same_company_members ON public.company_members;
CREATE POLICY same_company_members ON public.company_members
  FOR SELECT TO app_tenant
  USING (company_id = app.current_company_id());

GRANT SELECT ON public.companies, public.company_members TO app_tenant;

-- Политики привязаны к app_tenant. Роли anon/authenticated (PostgREST / supabase-js)
-- при включённом RLS без политик получают 0 строк. Если фронт ходит в БД напрямую,
-- политики для authenticated добавляются отдельно.

COMMIT;
