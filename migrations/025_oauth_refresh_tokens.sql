BEGIN;

ALTER TABLE public.platform_integrations
    ADD COLUMN IF NOT EXISTS encrypted_refresh_token varchar,
    ADD COLUMN IF NOT EXISTS expires_at timestamp with time zone;

COMMIT;
