-- Store sanitized review content while retaining opaque external identifiers.

ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS external_id varchar(255),
    ADD COLUMN IF NOT EXISTS author_hash varchar(32),
    ADD COLUMN IF NOT EXISTS author_display varchar(255),
    ADD COLUMN IF NOT EXISTS published_at timestamptz;

ALTER TABLE public.reviews
    DROP CONSTRAINT IF EXISTS reviews_privacy_summary_chk,
    DROP CONSTRAINT IF EXISTS reviews_author_display_chk,
    DROP CONSTRAINT IF EXISTS reviews_external_id_hash_chk,
    DROP CONSTRAINT IF EXISTS reviews_author_hash_chk;

ALTER TABLE public.reviews
    ADD CONSTRAINT reviews_author_display_chk
        CHECK (
            author_display IS NULL
            OR author_display IN ('Клиент', 'Анонимный клиент')
        ),
    ADD CONSTRAINT reviews_external_id_hash_chk
        CHECK (external_id IS NULL OR external_id ~ '^usr_[0-9a-f]{24}$'),
    ADD CONSTRAINT reviews_author_hash_chk
        CHECK (author_hash IS NULL OR author_hash ~ '^usr_[0-9a-f]{24}$');

CREATE UNIQUE INDEX IF NOT EXISTS uq_reviews_company_platform_external_id
    ON public.reviews (company_id, platform, external_id)
    WHERE external_id IS NOT NULL;
