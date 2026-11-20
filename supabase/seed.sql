-- SMARTTIMETABLE AI: BOOTSTRAP SEED
-- Strictly provisions ONLY the Timetable Officer account.
-- Zero mock data: All departments, sections, teachers, rooms, and clusters are created by the Officer.
-- Initial Credentials:
--   Officer ID: 17301
--   Initial Temporary Password: 8296060284

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
DECLARE
    officer_uuid UUID := '00000000-0000-0000-0000-000000017301';
    officer_email TEXT := 'officer17301@smarttimetable.local';
    officer_phone TEXT := '8296060284';
BEGIN
    -- 1. Insert into Supabase Auth users if not present
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'auth' AND table_name = 'users') THEN
        IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = officer_uuid OR email = officer_email) THEN
            INSERT INTO auth.users (
                id,
                instance_id,
                aud,
                role,
                email,
                encrypted_password,
                email_confirmed_at,
                phone,
                phone_confirmed_at,
                raw_app_meta_data,
                raw_user_meta_data,
                created_at,
                updated_at,
                confirmation_token
            ) VALUES (
                officer_uuid,
                '00000000-0000-0000-0000-000000000000',
                'authenticated',
                'authenticated',
                officer_email,
                crypt('8296060284', gen_salt('bf')),
                NOW(),
                officer_phone,
                NOW(),
                '{"provider":"email","providers":["email"]}'::jsonb,
                '{"role":"timetable_officer","employee_id":"17301","full_name":"Chief Timetable Officer"}'::jsonb,
                NOW(),
                NOW(),
                ''
            );
        END IF;
    END IF;

    -- 2. Insert into public.profiles
    INSERT INTO public.profiles (
        id,
        employee_id,
        full_name,
        role,
        phone_number,
        must_change_password,
        is_active,
        created_at,
        updated_at
    ) VALUES (
        officer_uuid,
        '17301',
        'Chief Timetable Officer',
        'timetable_officer',
        officer_phone,
        true,
        true,
        NOW(),
        NOW()
    )
    ON CONFLICT (employee_id) DO UPDATE SET
        role = 'timetable_officer',
        must_change_password = true,
        is_active = true,
        updated_at = NOW();

END $$;
