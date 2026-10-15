-- Shared semantic-cache schema used by app.core.llm_cache.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.llm_cache (
    text_hash varchar(64) PRIMARY KEY,
    text text NOT NULL,
    embedding vector(1536) NOT NULL,
    sentiment varchar(32) NOT NULL,
    sentiment_score double precision NOT NULL
        CHECK (sentiment_score >= 0 AND sentiment_score <= 1),
    tags text[] NOT NULL DEFAULT ARRAY[]::text[],
    suggested_response text,
    metadata text NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_llm_cache_expires_at
    ON public.llm_cache(expires_at);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.llm_cache TO app_tenant;
