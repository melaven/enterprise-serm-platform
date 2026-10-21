BEGIN;

ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS retry_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS is_dlq boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS dlq_reason text;

CREATE INDEX IF NOT EXISTS ix_reviews_dlq_pending
    ON public.reviews (company_id, created_at)
    WHERE is_dlq;

COMMIT;
