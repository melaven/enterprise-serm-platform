BEGIN;

ALTER TABLE public.review_replies
    ADD COLUMN IF NOT EXISTS status varchar(32),
    ADD COLUMN IF NOT EXISTS external_reply_id text,
    ADD COLUMN IF NOT EXISTS failure_reason text;

ALTER TABLE public.review_replies
    DROP CONSTRAINT IF EXISTS review_replies_status_check;
ALTER TABLE public.review_replies
    ADD CONSTRAINT review_replies_status_check
    CHECK (
        status IS NULL
        OR status IN (
            'queued_outbox',
            'publishing',
            'published',
            'publish_failed'
        )
    );

COMMIT;
