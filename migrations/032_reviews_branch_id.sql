-- Add branch_id column to reviews table for multi-branch support
-- Zero-downtime migration: nullable column added first, then backfilled

-- Step 1: Add nullable branch_id column
ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS branch_id uuid;

-- Step 2: Create composite index for tenant + branch queries
CREATE INDEX IF NOT EXISTS idx_reviews_tenant_branch
    ON public.reviews (company_id, branch_id);

-- Step 3: Backfill existing records with branch_id extracted from platform_url
-- This extracts the last UUID segment from platform_url (e.g., "https://2gis.ru/branch/123e4567-e89b-12d3-a456-426614174000")
-- If platform_url doesn't contain a UUID or is NULL, branch_id remains NULL
UPDATE public.reviews r
SET branch_id = (
    -- Extract UUID from platform_url using regex pattern
    -- Pattern matches standard UUID format in URL path
    (regexp_match(p.platform_url, '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'))[1]::uuid
)
FROM public.platforms p
WHERE r.platform_id = p.id
  AND r.branch_id IS NULL
  AND p.platform_url IS NOT NULL
  AND p.platform_url ~ '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';

-- Step 4: Add comment for documentation
COMMENT ON COLUMN public.reviews.branch_id IS 'Branch identifier for multi-location businesses. Extracted from platform.platform_url during migration 032.';
