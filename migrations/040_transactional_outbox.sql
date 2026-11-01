CREATE TABLE IF NOT EXISTS public.outbox_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type varchar(100) NOT NULL,
    payload jsonb NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processed', 'failed')),
    created_at timestamp NOT NULL DEFAULT now(),
    CONSTRAINT outbox_events_payload_tenant_id_chk
        CHECK (
            payload ->> 'tenant_id'
                ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        )
);

CREATE INDEX IF NOT EXISTS ix_outbox_events_pending_created_at
    ON public.outbox_events (created_at, id)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS ix_outbox_events_pending_tenant
    ON public.outbox_events ((payload ->> 'tenant_id'))
    WHERE status = 'pending';

ALTER TABLE public.outbox_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS outbox_events_tenant_insert
    ON public.outbox_events;
CREATE POLICY outbox_events_tenant_insert
    ON public.outbox_events
    FOR INSERT TO app_tenant
    WITH CHECK (payload ->> 'tenant_id' = app.current_company_id()::text);

DROP POLICY IF EXISTS outbox_events_tenant_select
    ON public.outbox_events;
CREATE POLICY outbox_events_tenant_select
    ON public.outbox_events
    FOR SELECT TO app_tenant
    USING (payload ->> 'tenant_id' = app.current_company_id()::text);

GRANT SELECT, INSERT ON public.outbox_events TO app_tenant;
REVOKE ALL ON public.outbox_events FROM PUBLIC;

CREATE OR REPLACE FUNCTION public.pending_outbox_tenants()
RETURNS TABLE (tenant_id uuid)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
    SELECT DISTINCT (event.payload ->> 'tenant_id')::uuid
    FROM public.outbox_events AS event
    WHERE event.status = 'pending'
$function$;

CREATE OR REPLACE FUNCTION public.claim_outbox_events(p_batch_size integer)
RETURNS TABLE (id uuid, event_type varchar, payload jsonb)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
    SELECT event.id, event.event_type, event.payload
    FROM public.outbox_events AS event
    WHERE event.status = 'pending'
      AND event.payload ->> 'tenant_id' = app.current_company_id()::text
    ORDER BY event.created_at, event.id
    LIMIT LEAST(GREATEST(p_batch_size, 1), 100)
    FOR UPDATE OF event SKIP LOCKED
$function$;

CREATE OR REPLACE FUNCTION public.set_outbox_event_status(
    p_event_id uuid,
    p_status varchar
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
BEGIN
    IF p_status NOT IN ('processed', 'failed') THEN
        RAISE EXCEPTION 'Invalid outbox status: %', p_status;
    END IF;

    UPDATE public.outbox_events
    SET status = p_status
    WHERE id = p_event_id
      AND status = 'pending'
      AND payload ->> 'tenant_id' = app.current_company_id()::text;

    RETURN FOUND;
END
$function$;

REVOKE ALL ON FUNCTION public.pending_outbox_tenants() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.claim_outbox_events(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.set_outbox_event_status(uuid, varchar) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.pending_outbox_tenants() TO app_tenant;
GRANT EXECUTE ON FUNCTION public.claim_outbox_events(integer) TO app_tenant;
GRANT EXECUTE ON FUNCTION public.set_outbox_event_status(uuid, varchar)
    TO app_tenant;

COMMENT ON TABLE public.outbox_events IS
    'Transactional events awaiting delivery to background workers.';
