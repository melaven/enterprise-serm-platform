-- DLQ для ARQ. Пишет только воркер через service_role (обходит RLS).
CREATE TABLE IF NOT EXISTS public.dead_letter_queue (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id         text        NOT NULL UNIQUE,   -- защита от дублей при повторной доставке
    job_name       text        NOT NULL,
    correlation_id text        NOT NULL,
    args           jsonb       NOT NULL DEFAULT '[]'::jsonb,
    kwargs         jsonb       NOT NULL DEFAULT '{}'::jsonb,
    error_message  text        NOT NULL,
    traceback      text        NOT NULL,
    status         text        NOT NULL DEFAULT 'pending_review'
                   CHECK (status IN ('pending_review', 'requeued', 'discarded')),
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS dead_letter_queue_status_created_idx
    ON public.dead_letter_queue (status, created_at DESC);
CREATE INDEX IF NOT EXISTS dead_letter_queue_correlation_idx
    ON public.dead_letter_queue (correlation_id);

-- args/kwargs/traceback могут содержать данные клиентов: закрываем от клиентских ролей.
ALTER TABLE public.dead_letter_queue ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.dead_letter_queue FROM anon, authenticated;
-- Политик нет намеренно: доступ только у service_role.
