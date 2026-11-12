ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS is_archived boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS ix_reviews_company_archived_created
    ON public.reviews (company_id, is_archived, created_at DESC);
