BEGIN;

ALTER TABLE public.api_keys
    ADD COLUMN IF NOT EXISTS last_used_at timestamp with time zone;

CREATE OR REPLACE FUNCTION public.record_api_key_usage_batch(
    p_key_hashes text[],
    p_used_at double precision[]
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    updated_count integer;
BEGIN
    IF cardinality(p_key_hashes) IS DISTINCT FROM cardinality(p_used_at) THEN
        RAISE EXCEPTION 'API key usage batch arrays must have equal lengths';
    END IF;

    UPDATE public.api_keys AS api_key
    SET last_used_at = GREATEST(
        COALESCE(api_key.last_used_at, '-infinity'::timestamptz),
        to_timestamp(LEAST(usage.used_at, extract(epoch FROM statement_timestamp())))
    )
    FROM unnest(p_key_hashes, p_used_at) AS usage(key_hash, used_at)
    WHERE api_key.key_hash = usage.key_hash
      AND api_key.revoked_at IS NULL;

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RETURN updated_count;
END;
$$;

REVOKE ALL ON FUNCTION public.record_api_key_usage_batch(text[], double precision[])
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.record_api_key_usage_batch(text[], double precision[])
    TO app_tenant;

COMMIT;
