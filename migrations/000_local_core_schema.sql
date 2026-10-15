-- Bootstrap the application schema for a local PostgreSQL/Supabase-compatible DB.
-- Supabase auth objects are stubbed only to preserve the company_members FK and hook.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS app;

DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'supabase_auth_admin') THEN
        CREATE ROLE supabase_auth_admin NOLOGIN;
    END IF;
END;
$roles$;

CREATE TABLE IF NOT EXISTS auth.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text UNIQUE,
    raw_user_meta_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.companies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(255) NOT NULL,
    average_check double precision NOT NULL DEFAULT 0,
    margin_percent double precision NOT NULL DEFAULT 0,
    cac double precision NOT NULL DEFAULT 0,
    base_ltv double precision NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS average_check double precision NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS margin_percent double precision NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cac double precision NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS base_ltv double precision NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS public.platforms (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    name varchar(255) NOT NULL,
    platform_url varchar(500),
    monthly_views integer NOT NULL DEFAULT 0,
    conversion_rate double precision NOT NULL DEFAULT 0,
    cac_on_platform double precision NOT NULL DEFAULT 0,
    average_rating double precision NOT NULL DEFAULT 0
);

ALTER TABLE public.platforms
    ADD COLUMN IF NOT EXISTS company_id uuid,
    ADD COLUMN IF NOT EXISTS platform_url varchar(500),
    ADD COLUMN IF NOT EXISTS monthly_views integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS conversion_rate double precision NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cac_on_platform double precision NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS average_rating double precision NOT NULL DEFAULT 0;

DO $types$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typname = 'review_status'
    ) THEN
        CREATE TYPE public.review_status AS ENUM (
            'new', 'si_processing', 'resolved', 'lost'
        );
    END IF;
END;
$types$;

CREATE TABLE IF NOT EXISTS public.reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id uuid NOT NULL REFERENCES public.platforms(id) ON DELETE CASCADE,
    company_id uuid REFERENCES public.companies(id) ON DELETE CASCADE,
    external_review_id varchar(255),
    platform varchar(255),
    author_name varchar(255) NOT NULL DEFAULT 'Аноним',
    rating integer NOT NULL CHECK (rating >= 0 AND rating <= 5),
    text text NOT NULL DEFAULT '',
    status public.review_status NOT NULL DEFAULT 'new',
    financial_impact double precision NOT NULL DEFAULT 0,
    si_response text,
    sentiment varchar(20),
    tags jsonb NOT NULL DEFAULT '[]'::jsonb,
    is_critical boolean NOT NULL DEFAULT false,
    auto_reply text,
    ai_pending boolean NOT NULL DEFAULT false,
    ai_error text,
    raw_metadata jsonb,
    reply_text text,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS platform_id uuid,
    ADD COLUMN IF NOT EXISTS company_id uuid,
    ADD COLUMN IF NOT EXISTS external_review_id varchar(255),
    ADD COLUMN IF NOT EXISTS platform varchar(255),
    ADD COLUMN IF NOT EXISTS author_name varchar(255) NOT NULL DEFAULT 'Аноним',
    ADD COLUMN IF NOT EXISTS rating integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS text text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS status public.review_status NOT NULL DEFAULT 'new',
    ADD COLUMN IF NOT EXISTS financial_impact double precision NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS si_response text,
    ADD COLUMN IF NOT EXISTS sentiment varchar(20),
    ADD COLUMN IF NOT EXISTS tags jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS is_critical boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS auto_reply text,
    ADD COLUMN IF NOT EXISTS ai_pending boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS ai_error text,
    ADD COLUMN IF NOT EXISTS raw_metadata jsonb,
    ADD COLUMN IF NOT EXISTS reply_text text,
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

DO $foreign_keys$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.platforms'::regclass
          AND conname = 'fk_platforms_company'
    ) THEN
        ALTER TABLE public.platforms
            ADD CONSTRAINT fk_platforms_company
            FOREIGN KEY (company_id)
            REFERENCES public.companies(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.reviews'::regclass
          AND conname = 'fk_reviews_platform'
    ) THEN
        ALTER TABLE public.reviews
            ADD CONSTRAINT fk_reviews_platform
            FOREIGN KEY (platform_id)
            REFERENCES public.platforms(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.reviews'::regclass
          AND conname = 'fk_reviews_company'
    ) THEN
        ALTER TABLE public.reviews
            ADD CONSTRAINT fk_reviews_company
            FOREIGN KEY (company_id)
            REFERENCES public.companies(id) ON DELETE CASCADE;
    END IF;
END;
$foreign_keys$;

UPDATE public.reviews r
SET company_id = p.company_id
FROM public.platforms p
WHERE r.platform_id = p.id AND r.company_id IS NULL;

DO $validate$
BEGIN
    IF EXISTS (SELECT 1 FROM public.platforms WHERE company_id IS NULL) THEN
        RAISE EXCEPTION
            'Cannot enable tenant RLS: platforms.company_id contains NULL. '
            'Backfill platforms before migrating.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.reviews
        WHERE company_id IS NULL OR platform_id IS NULL
    ) THEN
        RAISE EXCEPTION
            'Cannot enable tenant RLS: reviews have no tenant or platform. '
            'Backfill or remove orphan review rows before migrating.';
    END IF;
END;
$validate$;

ALTER TABLE public.platforms ALTER COLUMN company_id SET NOT NULL;
ALTER TABLE public.reviews
    ALTER COLUMN company_id SET NOT NULL,
    ALTER COLUMN platform_id SET NOT NULL;

CREATE TABLE IF NOT EXISTS public.company_members (
    user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    role varchar(50) NOT NULL DEFAULT 'member',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.financial_losses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    review_id uuid REFERENCES public.reviews(id) ON DELETE SET NULL,
    amount double precision NOT NULL DEFAULT 0,
    description text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_platforms_company_id
    ON public.platforms(company_id);
CREATE INDEX IF NOT EXISTS ix_reviews_company_id
    ON public.reviews(company_id);
CREATE INDEX IF NOT EXISTS ix_company_members_company_id
    ON public.company_members(company_id);
CREATE INDEX IF NOT EXISTS ix_financial_losses_company_id
    ON public.financial_losses(company_id);
