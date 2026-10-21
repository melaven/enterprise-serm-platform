BEGIN;

DO $migration$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'reviews'
          AND column_name = 'ai_attempts'
    ) THEN
        EXECUTE
            'UPDATE public.reviews '
            'SET retry_count = GREATEST(retry_count, COALESCE(ai_attempts, 0))';
    END IF;
END;
$migration$;

UPDATE public.reviews
SET dlq_reason = 'legacy_dlq'
WHERE is_dlq IS TRUE AND dlq_reason IS NULL;

DROP INDEX IF EXISTS public.ix_reviews_dlq_pending;

ALTER TABLE public.reviews
    DROP COLUMN IF EXISTS ai_attempts,
    DROP COLUMN IF EXISTS is_dlq;

CREATE INDEX IF NOT EXISTS ix_reviews_dlq_pending
    ON public.reviews (company_id, created_at)
    WHERE dlq_reason IS NOT NULL;

COMMIT;
