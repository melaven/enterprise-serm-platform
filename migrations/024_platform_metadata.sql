BEGIN;

ALTER TABLE public.platform_integrations
    ADD COLUMN IF NOT EXISTS meta_config jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMIT;
