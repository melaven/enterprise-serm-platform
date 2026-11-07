ALTER TABLE public.outbox_events
    ADD COLUMN IF NOT EXISTS priority integer NOT NULL DEFAULT 1;

ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS generated_reply text;
