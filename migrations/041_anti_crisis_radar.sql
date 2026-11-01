DO $migration$
BEGIN
    CREATE TYPE public.risk_level AS ENUM (
        'safe',
        'warning',
        'critical_risk'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$migration$;

DO $migration$
BEGIN
    CREATE TYPE public.response_strategy_type AS ENUM (
        'legal_strict',
        'appeasement',
        'info_request'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$migration$;

ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS risk_level public.risk_level
    NOT NULL DEFAULT 'safe';

CREATE TABLE IF NOT EXISTS public.ai_response_drafts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL
        REFERENCES public.companies(id) ON DELETE CASCADE,
    review_id uuid NOT NULL,
    strategy_type public.response_strategy_type NOT NULL,
    content text NOT NULL,
    is_approved boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_ai_response_drafts_review_tenant
        FOREIGN KEY (review_id, tenant_id)
        REFERENCES public.reviews(id, company_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_ai_response_drafts_tenant_id
    ON public.ai_response_drafts (tenant_id);
CREATE INDEX IF NOT EXISTS ix_ai_response_drafts_review_id
    ON public.ai_response_drafts (review_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_response_drafts_tenant_review_strategy
    ON public.ai_response_drafts (tenant_id, review_id, strategy_type);

ALTER TABLE public.ai_response_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_response_drafts FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_response_drafts_tenant_isolation
    ON public.ai_response_drafts;
CREATE POLICY ai_response_drafts_tenant_isolation
    ON public.ai_response_drafts
    FOR ALL TO app_tenant
    USING (tenant_id = app.current_company_id())
    WITH CHECK (tenant_id = app.current_company_id());

GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.ai_response_drafts TO app_tenant;
REVOKE ALL ON public.ai_response_drafts FROM PUBLIC;

COMMENT ON TABLE public.ai_response_drafts IS
    'Tenant-scoped AI response drafts for preventive review handling.';
