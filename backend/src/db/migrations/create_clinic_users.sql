-- ============================================================
-- Bytelytic Clinic OS — clinic_users table
-- Supabase SQL Editor mein yeh SQL run karo
-- ============================================================

-- 1. clinic_users table
CREATE TABLE IF NOT EXISTS public.clinic_users (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id         UUID        NOT NULL REFERENCES public.clinics(id) ON DELETE CASCADE,
    supabase_user_id  UUID        UNIQUE NOT NULL,   -- Supabase auth.users.id
    email             TEXT        NOT NULL,
    name              TEXT,
    role              TEXT        NOT NULL DEFAULT 'front_desk'
                      CHECK (role IN ('owner', 'doctor', 'front_desk', 'read_only')),
    is_active         BOOLEAN     NOT NULL DEFAULT true,
    invited_by        UUID        REFERENCES public.clinic_users(id) ON DELETE SET NULL,
    joined_at         TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Index for fast lookup by user_id + clinic_id
CREATE INDEX IF NOT EXISTS idx_clinic_users_user_clinic
    ON public.clinic_users (supabase_user_id, clinic_id);

CREATE INDEX IF NOT EXISTS idx_clinic_users_clinic
    ON public.clinic_users (clinic_id);

-- 3. Updated_at auto-update trigger
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS clinic_users_updated_at ON public.clinic_users;
CREATE TRIGGER clinic_users_updated_at
    BEFORE UPDATE ON public.clinic_users
    FOR EACH ROW EXECUTE PROCEDURE public.set_updated_at();

-- 4. Row Level Security (RLS)
ALTER TABLE public.clinic_users ENABLE ROW LEVEL SECURITY;

-- Sirf apne clinic ke users dekh sako
CREATE POLICY "clinic_users_select" ON public.clinic_users
    FOR SELECT USING (
        clinic_id IN (
            SELECT id FROM public.clinics
            WHERE owner_email = auth.jwt() ->> 'email'
        )
    );

-- Sirf owner insert kar sakta hai
CREATE POLICY "clinic_users_insert" ON public.clinic_users
    FOR INSERT WITH CHECK (
        clinic_id IN (
            SELECT id FROM public.clinics
            WHERE owner_email = auth.jwt() ->> 'email'
        )
    );

-- Owner update bhi kar sakta hai
CREATE POLICY "clinic_users_update" ON public.clinic_users
    FOR UPDATE USING (
        clinic_id IN (
            SELECT id FROM public.clinics
            WHERE owner_email = auth.jwt() ->> 'email'
        )
    );

-- 5. Service role (backend) ko RLS bypass karne do — yeh automatically hota hai
--    agar SUPABASE_SERVICE_KEY use ho rahi hai (jo hamara backend karta hai)

-- ============================================================
-- Existing clinic owners ko clinic_users mein insert karo
-- (Yeh ek-baar run karo taake purane accounts bhi cover hon)
-- ============================================================

INSERT INTO public.clinic_users (clinic_id, supabase_user_id, email, name, role, joined_at)
SELECT
    c.id                        AS clinic_id,
    u.id                        AS supabase_user_id,
    c.owner_email               AS email,
    COALESCE(c.name, c.owner_email) AS name,
    'owner'                     AS role,
    c.created_at                AS joined_at
FROM public.clinics c
JOIN auth.users u ON u.email = c.owner_email
ON CONFLICT (supabase_user_id) DO NOTHING;

-- ============================================================
-- Verify: yeh query run karo check karne ke liye
-- ============================================================
-- SELECT cu.email, cu.role, c.name as clinic_name
-- FROM public.clinic_users cu
-- JOIN public.clinics c ON c.id = cu.clinic_id;
