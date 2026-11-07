ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS reply_status varchar(20) NOT NULL DEFAULT 'pending';