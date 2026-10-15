-- Persist the structured AI enrichment produced for each review.
-- Apply as the migration role, not as app_tenant.

BEGIN;

ALTER TABLE public.reviews
  ADD COLUMN IF NOT EXISTS sentiment varchar(20),
  ADD COLUMN IF NOT EXISTS tags jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS is_critical boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS auto_reply text,
  ADD COLUMN IF NOT EXISTS ai_pending boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS ai_error text;

COMMIT;
