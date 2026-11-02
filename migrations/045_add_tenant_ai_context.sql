ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS tone_of_voice text DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS compensation_policy text DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS support_channel varchar DEFAULT NULL;
