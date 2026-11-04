ALTER TABLE public.outbox_events
    ADD COLUMN IF NOT EXISTS processing_at timestamptz;

ALTER TABLE public.outbox_events
    DROP CONSTRAINT IF EXISTS outbox_events_status_check;

ALTER TABLE public.outbox_events
    ADD CONSTRAINT outbox_events_status_check
    CHECK (status IN ('pending', 'processing', 'processed', 'failed'));

CREATE INDEX IF NOT EXISTS ix_outbox_events_tenant_status_processing_at
    ON public.outbox_events (
        (payload ->> 'tenant_id'),
        status,
        processing_at,
        created_at,
        id
    );

CREATE OR REPLACE FUNCTION public.pending_outbox_tenants()
RETURNS TABLE (tenant_id uuid)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
    SELECT DISTINCT (event.payload ->> 'tenant_id')::uuid
    FROM public.outbox_events AS event
    WHERE event.status = 'pending'
       OR (
            event.status = 'processing'
            AND event.processing_at < now() - interval '5 minutes'
       )
$function$;

CREATE OR REPLACE FUNCTION public.claim_outbox_events(p_batch_size integer)
RETURNS TABLE (id uuid, event_type varchar, payload jsonb)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
BEGIN
    RETURN QUERY
    WITH candidates AS (
        SELECT event.id
        FROM public.outbox_events AS event
        WHERE event.payload ->> 'tenant_id' = app.current_company_id()::text
          AND (
                event.status = 'pending'
                OR (
                    event.status = 'processing'
                    AND event.processing_at < now() - interval '5 minutes'
                )
          )
        ORDER BY event.created_at, event.id
        LIMIT LEAST(GREATEST(p_batch_size, 1), 100)
        FOR UPDATE OF event SKIP LOCKED
    )
    UPDATE public.outbox_events AS event
    SET status = 'processing',
        processing_at = now()
    FROM candidates
    WHERE event.id = candidates.id
    RETURNING event.id, event.event_type, event.payload;
END
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
    IF p_status NOT IN ('pending', 'processed', 'failed') THEN
        RAISE EXCEPTION 'Invalid outbox status: %', p_status;
    END IF;

    UPDATE public.outbox_events
    SET status = p_status,
        processing_at = NULL
    WHERE id = p_event_id
      AND status = 'processing'
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
