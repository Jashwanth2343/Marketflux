-- Enable row level security on every application table.
--
-- The frontend ships the Supabase anon key, so any table in `public` without
-- RLS is readable through the Data API. The backend uses the service role
-- (bypasses RLS) or the postgres connection string (table owner, bypasses RLS
-- unless FORCE is set). Do not FORCE row level security: that would block the
-- backend's direct Postgres connection, which does not set auth.uid().
--
-- Policies are for the `authenticated` role only. `anon` has no policies.
-- Tables without a user owner are service-role only (RLS on, no policy).

-- ---------------------------------------------------------------------------
-- Move the signup trigger out of the exposed public schema.
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION private.handle_new_user()
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
    RAISE WARNING 'handle_new_user failed for %: %', NEW.id, SQLERRM;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION private.handle_new_user();

DROP FUNCTION IF EXISTS public.handle_new_user();

GRANT USAGE ON SCHEMA private TO supabase_auth_admin;
GRANT EXECUTE ON FUNCTION private.handle_new_user() TO supabase_auth_admin;

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.owns_text(owner TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    SELECT owner IS NOT NULL AND owner = (SELECT auth.uid())::text;
$$;

REVOKE ALL ON FUNCTION public.owns_text(TEXT) FROM PUBLIC, anon, authenticated;

-- ---------------------------------------------------------------------------
-- Enable RLS. Missing tables are skipped so this can re-run on a partial DB.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'profiles', 'user_consent', 'personalities', 'trade_proposals', 'audit_events',
        'activity_events', 'pilot_memory', 'journal_entries', 'drift_flags',
        'portfolio_snapshots', 'workflow_checkpoints',
        'daily_briefs', 'research_runs', 'signal_events', 'ticker_workspaces',
        'saved_theses', 'watchlist_items', 'competitor_profiles', 'terminal_sessions',
        'strategy_proposals', 'execution_approvals', 'paper_orders', 'paper_positions',
        'model_usage_events', 'research_documents', 'theses', 'thesis_revisions',
        'evidence_blocks', 'memos', 'policy_rules', 'paper_trades',
        'agent_runs', 'agent_run_steps', 'backtest_runs',
        'ledger_theses', 'ledger_audit', 'ledger_daily_closes'
    ]
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = tbl
        ) THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl);
        END IF;
    END LOOP;
END $$;

-- Drop the old checkpoint policy that allowed every role through.
DROP POLICY IF EXISTS checkpoints_service ON public.workflow_checkpoints;

-- Service-role-only tables: RLS on, no policy, and no grants for the browser roles.
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'workflow_checkpoints', 'signal_events', 'ticker_workspaces',
        'competitor_profiles', 'research_documents', 'ledger_daily_closes'
    ]
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = tbl
        ) THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon, authenticated', tbl);
        END IF;
    END LOOP;
END $$;

-- Per-user policies. FOR ALL needs both USING and WITH CHECK.
DO $$
DECLARE
    spec RECORD;
BEGIN
    FOR spec IN
        SELECT * FROM (VALUES
            ('profiles', 'id = (SELECT auth.uid())'),
            ('user_consent', 'user_id = (SELECT auth.uid())'),
            ('trade_proposals', 'user_id = (SELECT auth.uid())'),
            ('pilot_memory', 'user_id = (SELECT auth.uid())'),
            ('portfolio_snapshots', 'user_id = (SELECT auth.uid())'),
            ('audit_events', 'user_id = (SELECT auth.uid())'),
            ('activity_events', 'user_id = (SELECT auth.uid())'),
            ('daily_briefs', 'public.owns_text(owner_user_id)'),
            ('research_runs', 'public.owns_text(owner_user_id)'),
            ('saved_theses', 'public.owns_text(owner_user_id)'),
            ('watchlist_items', 'public.owns_text(owner_user_id)'),
            ('terminal_sessions', 'public.owns_text(owner_user_id)'),
            ('strategy_proposals', 'public.owns_text(owner_user_id)'),
            ('execution_approvals', 'public.owns_text(owner_user_id)'),
            ('paper_orders', 'public.owns_text(owner_user_id)'),
            ('paper_positions', 'public.owns_text(owner_user_id)'),
            ('model_usage_events', 'public.owns_text(owner_user_id)'),
            ('theses', 'public.owns_text(owner_user_id)'),
            ('policy_rules', 'public.owns_text(owner_user_id)'),
            ('paper_trades', 'public.owns_text(owner_user_id)'),
            ('backtest_runs', 'public.owns_text(owner_user_id)'),
            ('agent_runs', 'public.owns_text(user_id)'),
            ('ledger_theses', 'public.owns_text(user_id)')
        ) AS t(table_name, predicate)
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = spec.table_name
        ) THEN
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', spec.table_name || '_owner', spec.table_name);
            EXECUTE format(
                'CREATE POLICY %I ON public.%I FOR ALL TO authenticated USING (%s) WITH CHECK (%s)',
                spec.table_name || '_owner', spec.table_name, spec.predicate, spec.predicate
            );
        END IF;
    END LOOP;
END $$;

-- Personalities: a user writes their own rows and can read public seeds.
DROP POLICY IF EXISTS personalities_owner ON public.personalities;
DROP POLICY IF EXISTS personalities_read ON public.personalities;
DROP POLICY IF EXISTS personalities_write ON public.personalities;
CREATE POLICY personalities_read ON public.personalities
    FOR SELECT TO authenticated
    USING (user_id = (SELECT auth.uid()) OR is_seed = true OR "public" = true);
CREATE POLICY personalities_owner ON public.personalities
    FOR ALL TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));

-- Child rows follow the parent owner.
DROP POLICY IF EXISTS journal_entries_owner ON public.journal_entries;
CREATE POLICY journal_entries_owner ON public.journal_entries
    FOR ALL TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.personalities p
        WHERE p.id = journal_entries.personality_id
          AND (p.user_id = (SELECT auth.uid()) OR p."public" = true OR p.is_seed = true)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM public.personalities p
        WHERE p.id = journal_entries.personality_id
          AND p.user_id = (SELECT auth.uid())
    ));

DROP POLICY IF EXISTS drift_flags_owner ON public.drift_flags;
CREATE POLICY drift_flags_owner ON public.drift_flags
    FOR ALL TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.personalities p
        WHERE p.id = drift_flags.personality_id AND p.user_id = (SELECT auth.uid())
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM public.personalities p
        WHERE p.id = drift_flags.personality_id AND p.user_id = (SELECT auth.uid())
    ));

DROP POLICY IF EXISTS thesis_revisions_owner ON public.thesis_revisions;
CREATE POLICY thesis_revisions_owner ON public.thesis_revisions
    FOR ALL TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.theses t
        WHERE t.id = thesis_revisions.thesis_id AND public.owns_text(t.owner_user_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM public.theses t
        WHERE t.id = thesis_revisions.thesis_id AND public.owns_text(t.owner_user_id)
    ));

DROP POLICY IF EXISTS evidence_blocks_owner ON public.evidence_blocks;
CREATE POLICY evidence_blocks_owner ON public.evidence_blocks
    FOR ALL TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.theses t
        WHERE t.id = evidence_blocks.thesis_id AND public.owns_text(t.owner_user_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM public.theses t
        WHERE t.id = evidence_blocks.thesis_id AND public.owns_text(t.owner_user_id)
    ));

DROP POLICY IF EXISTS memos_owner ON public.memos;
CREATE POLICY memos_owner ON public.memos
    FOR ALL TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.theses t
        WHERE t.id = memos.thesis_id AND public.owns_text(t.owner_user_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM public.theses t
        WHERE t.id = memos.thesis_id AND public.owns_text(t.owner_user_id)
    ));

DROP POLICY IF EXISTS agent_run_steps_owner ON public.agent_run_steps;
CREATE POLICY agent_run_steps_owner ON public.agent_run_steps
    FOR ALL TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.agent_runs r
        WHERE r.id = agent_run_steps.run_id AND public.owns_text(r.user_id)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM public.agent_runs r
        WHERE r.id = agent_run_steps.run_id AND public.owns_text(r.user_id)
    ));

DROP POLICY IF EXISTS ledger_audit_owner ON public.ledger_audit;
CREATE POLICY ledger_audit_owner ON public.ledger_audit
    FOR SELECT TO authenticated
    USING (EXISTS (
        SELECT 1 FROM public.ledger_theses t
        WHERE t.id = ledger_audit.thesis_id AND public.owns_text(t.user_id)
    ));

-- Privileged functions must not be callable with the anon key.
DO $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN
        SELECT p.proname AS proname, p.oid::regprocedure AS sig
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname IN ('retrieve_memory', 'cleanup_expired_memory', 'promote_warm_to_cold')
    LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated', rec.sig);
        IF rec.proname = 'retrieve_memory' THEN
            EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role', rec.sig);
        END IF;
    END LOOP;
END $$;

-- Trigger and policy helpers are invoked as the signed-in user. They do not
-- take a caller-supplied user id, so EXECUTE for `authenticated` is safe.
GRANT EXECUTE ON FUNCTION public.owns_text(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.set_updated_at() TO authenticated;
REVOKE ALL ON FUNCTION public.owns_text(TEXT) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.set_updated_at() FROM PUBLIC, anon;
