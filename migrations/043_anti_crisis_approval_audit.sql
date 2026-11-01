ALTER TABLE public.ai_response_drafts
    ADD COLUMN IF NOT EXISTS approved_by text;

ALTER TABLE public.ai_response_drafts
    ADD COLUMN IF NOT EXISTS approved_at timestamptz;
