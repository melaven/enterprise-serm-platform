BEGIN;

UPDATE public.reviews
SET author_name = 'Автор отзыва',
    author_avatar_url = NULL,
    author_profile_url = NULL,
    external_review_id = NULL,
    text = CASE
        WHEN sentiment = 'POSITIVE' THEN 'Положительный отзыв'
        WHEN sentiment = 'NEGATIVE' THEN 'Негативный отзыв'
        WHEN sentiment = 'NEUTRAL' THEN 'Нейтральный отзыв'
        ELSE 'Отзыв'
    END || '; оценка ' || rating::text || '/5.',
    si_response = NULL,
    suggested_reply = NULL,
    auto_reply = NULL,
    reply_text = NULL,
    raw_metadata = '{}'::jsonb,
    tags = '[]'::jsonb,
    analysis_tags = '[]'::jsonb,
    ai_error = NULL,
    dlq_reason = NULL;

WITH ranked_reviews AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY company_id, platform_id, created_at, rating, text
            ORDER BY id
        ) AS duplicate_number
    FROM public.reviews
)
DELETE FROM public.reviews AS review
USING ranked_reviews
WHERE review.id = ranked_reviews.id
  AND ranked_reviews.duplicate_number > 1;

DROP INDEX IF EXISTS public.reviews_external_id_platform_uq;
DROP INDEX IF EXISTS public.uq_reviews_tenant_platform_external_id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_reviews_analytics_dedup
    ON public.reviews (company_id, platform_id, created_at, rating, text);

DO $cleanup$
BEGIN
    IF to_regclass('public.llm_cache') IS NOT NULL THEN
        DELETE FROM public.llm_cache;
    END IF;
END;
$cleanup$;

COMMIT;
