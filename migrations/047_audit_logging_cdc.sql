CREATE TABLE IF NOT EXISTS public.audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL
        REFERENCES public.companies (id) ON DELETE CASCADE,
    user_id uuid,
    action varchar(100) NOT NULL,
    ip_address varchar(45),
    timestamp timestamptz NOT NULL DEFAULT now(),
    table_name varchar(255),
    record_id uuid,
    old_data jsonb,
    new_data jsonb,
    changed_by_user_id uuid,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.audit_logs
    ADD COLUMN IF NOT EXISTS table_name varchar(255),
    ADD COLUMN IF NOT EXISTS record_id uuid,
    ADD COLUMN IF NOT EXISTS old_data jsonb,
    ADD COLUMN IF NOT EXISTS new_data jsonb,
    ADD COLUMN IF NOT EXISTS changed_by_user_id uuid,
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS ix_audit_logs_table_record_created
    ON public.audit_logs (table_name, record_id, created_at DESC);

CREATE OR REPLACE FUNCTION public.log_table_changes()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
DECLARE
    old_row jsonb;
    new_row jsonb;
    changed_record_id uuid;
    changed_tenant_id uuid;
    actor_id uuid;
BEGIN
    IF TG_OP = 'INSERT' THEN
        new_row := to_jsonb(NEW);
        changed_record_id := (new_row ->> 'id')::uuid;
        changed_tenant_id := COALESCE(
            new_row ->> 'company_id',
            new_row ->> 'tenant_id'
        )::uuid;
    ELSIF TG_OP = 'UPDATE' THEN
        old_row := to_jsonb(OLD);
        new_row := to_jsonb(NEW);
        changed_record_id := (new_row ->> 'id')::uuid;
        changed_tenant_id := COALESCE(
            new_row ->> 'company_id',
            new_row ->> 'tenant_id',
            old_row ->> 'company_id',
            old_row ->> 'tenant_id'
        )::uuid;
    ELSE
        old_row := to_jsonb(OLD);
        changed_record_id := (old_row ->> 'id')::uuid;
        changed_tenant_id := COALESCE(
            old_row ->> 'company_id',
            old_row ->> 'tenant_id'
        )::uuid;
    END IF;

    IF changed_record_id IS NULL THEN
        RAISE EXCEPTION 'Cannot audit %.% without a UUID id', TG_TABLE_SCHEMA, TG_TABLE_NAME;
    END IF;
    IF changed_tenant_id IS NULL THEN
        RAISE EXCEPTION 'Cannot audit %.% without a tenant ID', TG_TABLE_SCHEMA, TG_TABLE_NAME;
    END IF;
    actor_id := NULLIF(current_setting('app.current_user_id', true), '')::uuid;

    INSERT INTO public.audit_logs (
        tenant_id,
        user_id,
        timestamp,
        table_name,
        record_id,
        action,
        old_data,
        new_data,
        changed_by_user_id,
        created_at
    )
    VALUES (
        changed_tenant_id,
        actor_id,
        clock_timestamp(),
        TG_TABLE_NAME,
        changed_record_id,
        TG_OP,
        old_row,
        new_row,
        actor_id,
        clock_timestamp()
    );

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$function$;

GRANT EXECUTE ON FUNCTION public.log_table_changes() TO app_tenant;

DO $migration$
DECLARE
    table_to_audit text;
BEGIN
    FOREACH table_to_audit IN ARRAY ARRAY[
        'reviews',
        'ai_response_drafts',
        'anti_crisis_response_drafts',
        'platform_integrations'
    ] LOOP
        IF to_regclass(format('public.%I', table_to_audit)) IS NULL THEN
            RAISE EXCEPTION 'Required audit table public.% is missing', table_to_audit;
        END IF;

        EXECUTE format(
            'DROP TRIGGER IF EXISTS audit_log_changes ON public.%I',
            table_to_audit
        );
        EXECUTE format(
            'CREATE TRIGGER audit_log_changes '
            'AFTER INSERT OR UPDATE OR DELETE ON public.%I '
            'FOR EACH ROW EXECUTE FUNCTION public.log_table_changes()',
            table_to_audit
        );
    END LOOP;
END;
$migration$;
