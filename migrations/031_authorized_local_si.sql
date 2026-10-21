BEGIN;

DROP INDEX IF EXISTS public.ix_reviews_external_review_id;
DROP INDEX IF EXISTS public.ix_reviews_external_id;
DROP INDEX IF EXISTS public.reviews_external_id_platform_uq;
DROP INDEX IF EXISTS public.uq_reviews_tenant_platform_external_id;

UPDATE public.reviews
SET author_name = 'Автор отзыва',
    external_review_id = NULL,
    author_avatar_url = NULL,
    author_profile_url = NULL,
sentiment = CASE
    WHEN rating >= 4 THEN 'POSITIVE'
    WHEN rating = 3 THEN 'NEUTRAL'
    ELSE 'NEGATIVE'
END,
text = CASE
    WHEN rating >= 4 THEN 'Положительный отзыв; оценка ' || rating::text || '/5.'
    WHEN rating = 3 THEN 'Нейтральный отзыв; оценка ' || rating::text || '/5.'
    ELSE 'Негативный отзыв; оценка ' || rating::text || '/5.'
END,
    si_response = NULL,
    suggested_reply = NULL,
    auto_reply = NULL,
    reply_text = NULL,
    raw_metadata = '{}'::jsonb,
    tags = '[]'::jsonb,
    analysis_tags = '[]'::jsonb,
    ai_error = NULL,
    dlq_reason = NULL,
    threat_level = NULL,
    is_critical = false,
    is_analyzed = true,
    ai_pending = false;

ALTER TABLE public.reviews
    DROP COLUMN IF EXISTS external_review_id,
    DROP COLUMN IF EXISTS author_avatar_url,
    DROP COLUMN IF EXISTS author_profile_url;

CREATE UNIQUE INDEX IF NOT EXISTS uq_reviews_analytics_dedup
    ON public.reviews (company_id, platform_id, created_at, rating, text);

ALTER TABLE public.reviews
    DROP CONSTRAINT IF EXISTS reviews_privacy_summary_chk,
    DROP CONSTRAINT IF EXISTS reviews_privacy_author_chk,
    DROP CONSTRAINT IF EXISTS reviews_privacy_no_source_text_chk;

ALTER TABLE public.reviews
    ADD CONSTRAINT reviews_privacy_summary_chk
        CHECK (
            text IN (
                'Положительный отзыв; оценка ' || rating::text || '/5.',
                'Нейтральный отзыв; оценка ' || rating::text || '/5.',
                'Негативный отзыв; оценка ' || rating::text || '/5.'
            )
        ),
    ADD CONSTRAINT reviews_privacy_author_chk
        CHECK (author_name = 'Автор отзыва'),
    ADD CONSTRAINT reviews_privacy_no_source_text_chk
        CHECK (
            si_response IS NULL
            AND suggested_reply IS NULL
            AND auto_reply IS NULL
            AND reply_text IS NULL
            AND raw_metadata IS NOT DISTINCT FROM '{}'::jsonb
            AND tags <@ '["SERVICE", "PRODUCT_QUALITY", "DELIVERY", "PRICING", "OTHER"]'::jsonb
            AND analysis_tags <@ '["SERVICE", "PRODUCT_QUALITY", "DELIVERY", "PRICING", "OTHER"]'::jsonb
            AND ai_error IS NULL
            AND dlq_reason IS NULL
        );

DELETE FROM public.llm_cache;
DELETE FROM public.dead_letter_queue;

COMMIT;
