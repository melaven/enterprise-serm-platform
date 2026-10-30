ALTER TABLE public.reviews
    ALTER COLUMN platform_id DROP NOT NULL;

DROP INDEX IF EXISTS public.uq_reviews_analytics_dedup;
DROP INDEX IF EXISTS public.uq_reviews_company_platform_external_id;
DROP INDEX IF EXISTS public.uq_reviews_tenant_platform_external_id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_reviews_tenant_platform_external_id
    ON public.reviews (company_id, platform, external_id);
