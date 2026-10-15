-- Tenant-scoped platform statistics and review integrity constraints.

CREATE UNIQUE INDEX IF NOT EXISTS uq_platforms_company_name
    ON public.platforms(company_id, name);

CREATE UNIQUE INDEX IF NOT EXISTS uq_platforms_id_company
    ON public.platforms(id, company_id);

DROP INDEX IF EXISTS public.ix_reviews_external_review_id;
DROP INDEX IF EXISTS public.reviews_external_id_platform_uq;
ALTER TABLE public.reviews
    DROP CONSTRAINT IF EXISTS reviews_external_review_id_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_reviews_tenant_platform_external_id
    ON public.reviews(company_id, platform, external_review_id)
    WHERE external_review_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.platform_statistics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL,
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    average_rating double precision NOT NULL
        CHECK (average_rating >= 0 AND average_rating <= 5),
    rating_change double precision NOT NULL DEFAULT 0,
    review_count integer NOT NULL DEFAULT 0 CHECK (review_count >= 0),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_platform_statistics_platform
        FOREIGN KEY (platform_id)
        REFERENCES public.platforms(id) ON DELETE CASCADE,
    CONSTRAINT fk_platform_statistics_platform_tenant
        FOREIGN KEY (platform_id, company_id)
        REFERENCES public.platforms(id, company_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_platform_statistics_tenant_platform_recorded
    ON public.platform_statistics(company_id, platform_id, recorded_at);

DO $constraints$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.reviews'::regclass
          AND conname = 'fk_reviews_platform_tenant'
    ) THEN
        ALTER TABLE public.reviews
            ADD CONSTRAINT fk_reviews_platform_tenant
            FOREIGN KEY (platform_id, company_id)
            REFERENCES public.platforms(id, company_id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.reviews'::regclass
          AND conname = 'ck_reviews_rating_range'
    ) THEN
        ALTER TABLE public.reviews
            ADD CONSTRAINT ck_reviews_rating_range
            CHECK (rating >= 0 AND rating <= 5);
    END IF;
END;
$constraints$;

ALTER TABLE public.platforms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_statistics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON public.platforms;
CREATE POLICY tenant_isolation ON public.platforms
    FOR ALL TO app_tenant
    USING (company_id = app.current_company_id())
    WITH CHECK (company_id = app.current_company_id());

DROP POLICY IF EXISTS tenant_isolation ON public.platform_statistics;
CREATE POLICY tenant_isolation ON public.platform_statistics
    FOR ALL TO app_tenant
    USING (company_id = app.current_company_id())
    WITH CHECK (company_id = app.current_company_id());

GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.platform_statistics TO app_tenant;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.platforms TO app_tenant;
