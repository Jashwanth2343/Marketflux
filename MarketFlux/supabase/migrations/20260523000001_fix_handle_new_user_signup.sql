-- ===========================================================================
-- Fix: signup fails with 500 "Database error saving new user"
-- ===========================================================================
-- Root cause: on_auth_user_created (AFTER INSERT ON auth.users) calls
-- handle_new_user(), which inserted into the UNqualified table "profiles".
-- GoTrue fires this trigger as role supabase_auth_admin, whose search_path
-- does not include `public`, so "profiles" cannot be resolved -> the insert
-- raises -> the whole auth.users insert rolls back -> 500 on signup.
--
-- Fix: schema-qualify (public.profiles), pin search_path, and wrap the insert
-- so a profile-creation problem can NEVER block account creation again.
-- ===========================================================================

-- Safety net in case the table was never created on this project.
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    display_name TEXT,
    avatar_url TEXT,
    alpaca_account_id TEXT,
    alpaca_mode TEXT DEFAULT 'trading',
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.profiles (id, email, display_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1))
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    -- Never let profile creation block auth signup.
    RAISE WARNING 'handle_new_user failed for %: %', NEW.id, SQLERRM;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Defensive grants (SECURITY DEFINER runs as owner, but harmless to be explicit).
GRANT USAGE ON SCHEMA public TO supabase_auth_admin;
GRANT INSERT, SELECT ON public.profiles TO supabase_auth_admin;
