DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type AS t
        JOIN pg_namespace AS schema_namespace ON schema_namespace.oid = t.typnamespace
        WHERE schema_namespace.nspname = 'public'
          AND t.typname = 'review_state'
    ) THEN
        CREATE TYPE public.review_state AS ENUM (
            'new',
            'analyzing',
            'auto_approved',
            'draft_pending',
            'escalated',
            'ignored',
            'approved',
            'publishing',
            'published',
            'publish_failed'
        );
    END IF;
END
$migration$;

ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS state public.review_state
        NOT NULL DEFAULT 'new',
    ADD COLUMN IF NOT EXISTS updated_at timestamptz
        NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS public.review_analysis_payloads (
    review_id uuid PRIMARY KEY
        REFERENCES public.reviews(id) ON DELETE CASCADE,
    company_id uuid NOT NULL
        REFERENCES public.companies(id) ON DELETE CASCADE,
    encrypted_text text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_review_analysis_payloads_company_id
    ON public.review_analysis_payloads (company_id);

ALTER TABLE public.review_analysis_payloads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.review_analysis_payloads FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS review_analysis_payloads_tenant_isolation
    ON public.review_analysis_payloads;
CREATE POLICY review_analysis_payloads_tenant_isolation
    ON public.review_analysis_payloads
    FOR ALL TO app_tenant
    USING (company_id = app.current_company_id())
    WITH CHECK (company_id = app.current_company_id());

GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.review_analysis_payloads TO app_tenant;

COMMENT ON TABLE public.review_analysis_payloads IS
    'Short-lived Fernet-encrypted review text for local asynchronous analysis.';
