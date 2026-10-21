BEGIN;

ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS author_avatar_url text,
    ADD COLUMN IF NOT EXISTS author_profile_url text;

UPDATE public.reviews
SET author_name = 'Анонимный клиент ' || substr(md5(id::text), 1, 6)
WHERE author_name NOT LIKE 'Анонимный клиент%';

ALTER TABLE public.reviews
    ALTER COLUMN author_avatar_url DROP NOT NULL,
    ALTER COLUMN author_profile_url DROP NOT NULL;

UPDATE public.reviews
SET author_avatar_url = NULL,
    author_profile_url = NULL;

COMMIT;
