BEGIN;

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS notification_email varchar(320);

ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS sentiment text,
    ADD COLUMN IF NOT EXISTS threat_level integer,
    ADD COLUMN IF NOT EXISTS suggested_reply text,
    ADD COLUMN IF NOT EXISTS analysis_tags jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS is_analyzed boolean NOT NULL DEFAULT false;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'reviews_sentiment_chk'
    ) THEN
        ALTER TABLE public.reviews
            ADD CONSTRAINT reviews_sentiment_chk
            CHECK (sentiment IS NULL OR sentiment IN ('POSITIVE', 'NEGATIVE', 'NEUTRAL'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'reviews_threat_level_chk'
    ) THEN
        ALTER TABLE public.reviews
            ADD CONSTRAINT reviews_threat_level_chk
            CHECK (threat_level IS NULL OR threat_level BETWEEN 1 AND 5);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'reviews_analysis_tags_chk'
    ) THEN
        ALTER TABLE public.reviews
            ADD CONSTRAINT reviews_analysis_tags_chk
            CHECK (jsonb_typeof(analysis_tags) = 'array');
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS reviews_pending_analysis_idx
    ON public.reviews (company_id, created_at)
    WHERE NOT is_analyzed;

COMMIT;
