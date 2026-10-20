-- Persist the threat level assigned by the sentiment intelligence pipeline.

ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS threat_level integer;

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_reviews_threat_level_range'
          AND conrelid = 'public.reviews'::regclass
    ) THEN
        ALTER TABLE public.reviews
            ADD CONSTRAINT ck_reviews_threat_level_range
            CHECK (threat_level IS NULL OR threat_level BETWEEN 1 AND 5)
            NOT VALID;
    END IF;
END
$migration$;

ALTER TABLE public.reviews
    VALIDATE CONSTRAINT ck_reviews_threat_level_range;
