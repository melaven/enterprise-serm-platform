ALTER TABLE public.outbox_events
    ADD COLUMN IF NOT EXISTS idempotency_key varchar(200);

CREATE UNIQUE INDEX IF NOT EXISTS uq_outbox_events_idempotency_key
    ON public.outbox_events (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_response_drafts_tenant_review_strategy
    ON public.ai_response_drafts (tenant_id, review_id, strategy_type);
