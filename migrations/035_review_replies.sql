DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_reviews_id_company_id'
          AND conrelid = 'public.reviews'::regclass
    ) THEN
        ALTER TABLE public.reviews
            ADD CONSTRAINT uq_reviews_id_company_id UNIQUE (id, company_id);
    END IF;
END
$migration$;

CREATE TABLE IF NOT EXISTS public.review_replies (
    review_id uuid PRIMARY KEY
        NOT NULL,
    company_id uuid NOT NULL
        REFERENCES public.companies(id) ON DELETE CASCADE,
    reply_text text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_review_replies_review_tenant
        FOREIGN KEY (review_id, company_id)
        REFERENCES public.reviews(id, company_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_review_replies_company_id
    ON public.review_replies (company_id);

ALTER TABLE public.review_replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.review_replies FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS review_replies_tenant_isolation
    ON public.review_replies;
CREATE POLICY review_replies_tenant_isolation
    ON public.review_replies
    FOR ALL TO app_tenant
    USING (company_id = app.current_company_id())
    WITH CHECK (company_id = app.current_company_id());

GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.review_replies TO app_tenant;

COMMENT ON TABLE public.review_replies IS
    'Tenant-scoped storage for moderated replies; reply text is kept outside privacy-constrained reviews.';
