-- 003_rls_smoke_test.sql
-- Запуск под postgres. Данных не создаёт, в конце ROLLBACK.
-- Для каждой компании, у которой есть строки в reviews, проверяет:
--   под app_tenant с её контекстом видно ровно её строки;
--   без контекста видно 0 строк.
BEGIN;

GRANT app_tenant TO CURRENT_USER;  -- нужно для SET ROLE внутри теста

DO $$
DECLARE
  c        uuid;
  expected bigint;
  seen     bigint;
BEGIN
  FOR c IN SELECT DISTINCT company_id FROM public.reviews LOOP
    SELECT count(*) INTO expected FROM public.reviews WHERE company_id = c;

    PERFORM set_config('app.company_id', c::text, true);
    SET LOCAL ROLE app_tenant;
    SELECT count(*) INTO seen FROM public.reviews;
    RESET ROLE;

    IF seen <> expected THEN
      RAISE EXCEPTION 'RLS leak: company % sees % rows, expected %',
        c, seen, expected;
    END IF;
  END LOOP;

  PERFORM set_config('app.company_id', '', true);
  SET LOCAL ROLE app_tenant;
  SELECT count(*) INTO seen FROM public.reviews;
  RESET ROLE;

  IF seen <> 0 THEN
    RAISE EXCEPTION 'RLS fail-open: % rows visible without tenant context', seen;
  END IF;

  RAISE NOTICE 'RLS OK';
END $$;

ROLLBACK;
