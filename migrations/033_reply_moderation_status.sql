-- Add reply_moderation_status enum and column to reviews table for FSM workflow

-- Step 1: Create enum type for reply moderation status
DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reply_moderation_status') THEN
        CREATE TYPE reply_moderation_status AS ENUM (
            'new',
            'drafted',
            'pending_moderation',
            'approved',
            'published'
        );
    END IF;
END
$migration$;

-- Step 2: Add column with default value
ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS moderation_status reply_moderation_status
    DEFAULT 'new'::reply_moderation_status
    NOT NULL;

-- Step 3: Add comment for documentation
COMMENT ON COLUMN public.reviews.moderation_status IS 'FSM status for reply moderation workflow: new -> drafted -> pending_moderation -> approved -> published';
COMMENT ON TYPE reply_moderation_status IS 'Enum for reply moderation finite state machine transitions';
