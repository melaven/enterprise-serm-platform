-- Preserve the existing anti-crisis records and give the generator its own table.
--   generation      - номер перегенерации отзыва (1, 2, ...); старые варианты получают status='superseded';
--   variant         - стратегия ответа: FORMAL / EMPATHETIC / ACTION_ORIENTED;
--   source          - 'llm' или 'fallback' (шаблон при сбое LLM); fallback_reason - короткий код без данных клиента;
--   status          - draft -> approved | rejected | superseded.
-- Инварианты в БД, а не только в коде (гонки воркеров и менеджеров решает индекс, не приложение):
--   * не более одного активного (draft/approved) варианта каждой стратегии на отзыв -> повтор ARQ-задачи не плодит дубли;
--   * не более одного approved на отзыв -> контракт 409 «другой менеджер успел раньше».
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.reviews') IS NULL THEN
    RAISE EXCEPTION 'public.reviews not found';
  END IF;
  IF to_regclass('public.anti_crisis_response_drafts') IS NULL
     AND to_regclass('public.ai_response_drafts') IS NOT NULL THEN
    ALTER TABLE public.ai_response_drafts RENAME TO anti_crisis_response_drafts;
  ELSIF to_regclass('public.anti_crisis_response_drafts') IS NOT NULL
        AND to_regclass('public.ai_response_drafts') IS NOT NULL THEN
    RAISE EXCEPTION 'Both anti-crisis and generator draft tables already exist';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.ai_response_drafts (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id       uuid        NOT NULL,
  company_id      uuid        NOT NULL DEFAULT app.current_company_id(),
  generation      integer     NOT NULL DEFAULT 1,
  variant         text        NOT NULL,
  content         text        NOT NULL,
  source          text        NOT NULL DEFAULT 'llm',
  fallback_reason text,
  model           text,
  prompt_version  text,
  status          text        NOT NULL DEFAULT 'draft',
  approved_by     uuid,
  approved_at     timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ai_response_drafts_variant_chk
    CHECK (variant IN ('FORMAL', 'EMPATHETIC', 'ACTION_ORIENTED')),
  CONSTRAINT ai_response_drafts_source_chk CHECK (source IN ('llm', 'fallback')),
  CONSTRAINT ai_response_drafts_status_chk
    CHECK (status IN ('draft', 'approved', 'rejected', 'superseded')),
  CONSTRAINT ai_response_drafts_content_len_chk CHECK (char_length(content) BETWEEN 1 AND 2000),
  CONSTRAINT ai_response_drafts_generation_chk CHECK (generation >= 1),
  CONSTRAINT ai_response_drafts_fallback_reason_chk
    CHECK ((source = 'fallback') = (fallback_reason IS NOT NULL)),
  CONSTRAINT ai_response_drafts_approved_chk
    CHECK ((status = 'approved') = (approved_at IS NOT NULL)),
  CONSTRAINT ai_response_drafts_generation_variant_uq UNIQUE (review_id, generation, variant),
  CONSTRAINT ai_response_drafts_review_company_fk
    FOREIGN KEY (review_id, company_id)
    REFERENCES public.reviews (id, company_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ai_response_drafts_one_active_variant_idx
  ON public.ai_response_drafts (review_id, variant)
  WHERE status IN ('draft', 'approved');

CREATE UNIQUE INDEX IF NOT EXISTS ai_response_drafts_one_approved_idx
  ON public.ai_response_drafts (review_id)
  WHERE status = 'approved';

CREATE INDEX IF NOT EXISTS ai_response_drafts_company_idx
  ON public.ai_response_drafts (company_id, created_at DESC);

-- Очередь перегенерации шаблонов: отзывы, где вместо LLM стоит fallback.
CREATE INDEX IF NOT EXISTS ai_response_drafts_fallback_idx
  ON public.ai_response_drafts (company_id, created_at)
  WHERE source = 'fallback' AND status = 'draft';

ALTER TABLE public.ai_response_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_response_drafts FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_select ON public.ai_response_drafts;
DROP POLICY IF EXISTS tenant_insert ON public.ai_response_drafts;
DROP POLICY IF EXISTS tenant_update ON public.ai_response_drafts;
DROP POLICY IF EXISTS tenant_delete ON public.ai_response_drafts;

-- review_id проверяется через reviews под её собственной RLS: нельзя прикрепить черновик к чужому отзыву.
CREATE POLICY tenant_select ON public.ai_response_drafts FOR SELECT TO app_tenant
  USING (company_id = (SELECT app.current_company_id()));
CREATE POLICY tenant_insert ON public.ai_response_drafts FOR INSERT TO app_tenant
  WITH CHECK (company_id = (SELECT app.current_company_id()));
CREATE POLICY tenant_update ON public.ai_response_drafts FOR UPDATE TO app_tenant
  USING (company_id = (SELECT app.current_company_id()))
  WITH CHECK (company_id = (SELECT app.current_company_id()));
CREATE POLICY tenant_delete ON public.ai_response_drafts FOR DELETE TO app_tenant
  USING (company_id = (SELECT app.current_company_id()));

GRANT SELECT, INSERT, UPDATE, DELETE ON public.ai_response_drafts TO app_tenant;

-- updated_at ведёт БД, а не приложение.
CREATE OR REPLACE FUNCTION public.ai_response_drafts_touch()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS ai_response_drafts_touch ON public.ai_response_drafts;
CREATE TRIGGER ai_response_drafts_touch BEFORE UPDATE ON public.ai_response_drafts
  FOR EACH ROW EXECUTE FUNCTION public.ai_response_drafts_touch();

COMMENT ON TABLE public.ai_response_drafts IS 'Черновики ответов на отзывы: 3 варианта на поколение генерации';
COMMENT ON COLUMN public.ai_response_drafts.fallback_reason IS 'Код причины шаблона (llm_timeout, malformed_output, ...); без данных клиента';

COMMIT;
