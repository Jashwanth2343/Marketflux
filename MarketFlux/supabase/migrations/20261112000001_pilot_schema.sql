-- Pilot / copilot tables (profiles, personalities, proposals, memory).
-- Canonical copy of the former backend/supabase/schema.sql.
-- Row level security is applied in 20261112000003_enable_rls.sql.
-- handle_new_user() stays in 20260523000001 (and is moved to the private
-- schema by the RLS migration). This file does not recreate it.
-- moddatetime / pg_cron are intentionally not required.

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- ===========================================================================
-- MarketFlux Supabase Schema
-- Primary brain: auth, copilot, memory (pgvector), portfolio tracking
-- Run via Supabase SQL Editor or supabase db push
-- ===========================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- ===========================================================================
-- PROFILES (extends auth.users)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    display_name TEXT,
    avatar_url TEXT,
    alpaca_account_id TEXT,          -- broker mode: per-user sub-account
    alpaca_mode TEXT DEFAULT 'trading',
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

DROP TRIGGER IF EXISTS profiles_updated_at ON profiles;
CREATE TRIGGER profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ===========================================================================
-- USER CONSENT (pilot paper trading agreement)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS user_consent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    accept_paper_only BOOLEAN NOT NULL DEFAULT false,
    accept_not_advice BOOLEAN NOT NULL DEFAULT false,
    accept_audit_logging BOOLEAN NOT NULL DEFAULT false,
    kill_phrase TEXT,
    granted_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id)
);

-- ===========================================================================
-- PERSONALITIES (AI portfolio manager personas)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS personalities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    is_seed BOOLEAN DEFAULT false,
    slug TEXT UNIQUE,
    name TEXT NOT NULL,
    mandate TEXT NOT NULL,
    universe TEXT[] NOT NULL DEFAULT '{}',
    signal_weights JSONB DEFAULT '{}',
    risk_policy JSONB DEFAULT '{}',
    cadence TEXT DEFAULT 'daily',
    initial_capital_usd FLOAT DEFAULT 25000.0,
    accent_color TEXT DEFAULT '#22c55e',
    avatar_glyph TEXT DEFAULT 'circle',
    paused BOOLEAN DEFAULT false,
    public BOOLEAN DEFAULT false,
    blocked_tickers TEXT[] DEFAULT '{}',
    blackout_dates TEXT[] DEFAULT '{}',
    user_notes TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

DROP TRIGGER IF EXISTS personalities_updated_at ON personalities;
CREATE TRIGGER personalities_updated_at
    BEFORE UPDATE ON personalities
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE INDEX IF NOT EXISTS idx_personalities_user ON personalities(user_id);
CREATE INDEX IF NOT EXISTS idx_personalities_slug ON personalities(slug);

-- ===========================================================================
-- TRADE PROPOSALS (the core copilot artifact)
-- ===========================================================================
DO $$ BEGIN
    CREATE TYPE proposal_status AS ENUM (
        'pending', 'approved', 'rejected', 'executed', 'failed', 'expired'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS trade_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    personality_id UUID NOT NULL REFERENCES personalities(id) ON DELETE CASCADE,
    personality_name TEXT,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    qty FLOAT NOT NULL,
    order_type TEXT DEFAULT 'market',
    quote_price FLOAT,
    proposed_notional FLOAT,
    stop_loss_price FLOAT,
    take_profit_price FLOAT,
    time_in_force TEXT DEFAULT 'day',
    thesis TEXT,
    conviction INT DEFAULT 0,
    invalidation TEXT,
    dissent_summary TEXT,

    -- Lifecycle
    status proposal_status NOT NULL DEFAULT 'pending',
    approved_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    expired_at TIMESTAMPTZ,

    -- Execution results
    alpaca_order_id TEXT,
    fill_price FLOAT,
    fill_qty FLOAT,

    -- Agent reasoning (stored as JSONB for flexibility)
    debate_transcript JSONB DEFAULT '[]',
    signal_snapshot JSONB DEFAULT '{}',
    risk_verdict JSONB DEFAULT '{}',
    policy_verdict JSONB DEFAULT '{}',
    catalyst_stress_test JSONB,
    agent_trace JSONB DEFAULT '[]',

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

DROP TRIGGER IF EXISTS proposals_updated_at ON trade_proposals;
CREATE TRIGGER proposals_updated_at
    BEFORE UPDATE ON trade_proposals
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE INDEX IF NOT EXISTS idx_proposals_user ON trade_proposals(user_id);
CREATE INDEX IF NOT EXISTS idx_proposals_personality ON trade_proposals(personality_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON trade_proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_ticker ON trade_proposals(ticker);
CREATE INDEX IF NOT EXISTS idx_proposals_created ON trade_proposals(created_at DESC);

-- ===========================================================================
-- AUDIT EVENTS (immutable trail)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID REFERENCES trade_proposals(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    event_type TEXT NOT NULL,
    actor TEXT,
    reason TEXT,
    payload JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_proposal ON audit_events(proposal_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at DESC);

-- ===========================================================================
-- ACTIVITY EVENTS (live "what the AI is thinking" stream)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS activity_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    personality_id UUID REFERENCES personalities(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    event_type TEXT NOT NULL,
    message TEXT,
    payload JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_activity_personality ON activity_events(personality_id);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_events(created_at DESC);

-- ===========================================================================
-- PILOT MEMORY (layered institutional knowledge with pgvector)
-- ===========================================================================
DO $$ BEGIN
    CREATE TYPE memory_layer AS ENUM ('hot', 'warm', 'cold');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS pilot_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    personality_id UUID NOT NULL REFERENCES personalities(id) ON DELETE CASCADE,
    layer memory_layer NOT NULL DEFAULT 'warm',
    category TEXT NOT NULL,
    ticker TEXT,
    content TEXT NOT NULL,
    importance FLOAT DEFAULT 0.5 CHECK (importance >= 0 AND importance <= 1),

    -- pgvector embedding for semantic retrieval
    embedding vector(1536),

    -- Metadata (flexible per category)
    metadata JSONB DEFAULT '{}',

    -- Lifecycle
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_user_personality ON pilot_memory(user_id, personality_id);
CREATE INDEX IF NOT EXISTS idx_memory_layer ON pilot_memory(layer);
CREATE INDEX IF NOT EXISTS idx_memory_ticker ON pilot_memory(ticker);
CREATE INDEX IF NOT EXISTS idx_memory_category ON pilot_memory(category);
CREATE INDEX IF NOT EXISTS idx_memory_expires ON pilot_memory(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_created ON pilot_memory(created_at DESC);

-- HNSW index for fast vector similarity search
CREATE INDEX IF NOT EXISTS idx_memory_embedding ON pilot_memory
    USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

-- ===========================================================================
-- JOURNAL ENTRIES (daily personality reflections)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    personality_id UUID NOT NULL REFERENCES personalities(id) ON DELETE CASCADE,
    entry_date DATE NOT NULL,
    summary TEXT,
    trades_reviewed INT DEFAULT 0,
    lessons JSONB DEFAULT '[]',
    mood TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(personality_id, entry_date)
);

CREATE INDEX IF NOT EXISTS idx_journal_personality ON journal_entries(personality_id);

-- ===========================================================================
-- DRIFT FLAGS (thesis drift detection)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS drift_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    personality_id UUID NOT NULL REFERENCES personalities(id) ON DELETE CASCADE,
    flag_type TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    message TEXT,
    resolved BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_drift_personality ON drift_flags(personality_id);

-- ===========================================================================
-- PORTFOLIO SNAPSHOTS (daily equity for charting)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    personality_id UUID REFERENCES personalities(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    equity FLOAT,
    cash FLOAT,
    buying_power FLOAT,
    unrealized_pl FLOAT,
    realized_pl FLOAT,
    positions JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, personality_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_user ON portfolio_snapshots(user_id, snapshot_date DESC);

-- ===========================================================================
-- WORKFLOW CHECKPOINTS (LangGraph-compatible agent state persistence)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS workflow_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id TEXT NOT NULL,
    step TEXT NOT NULL,
    state JSONB NOT NULL DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON workflow_checkpoints(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_checkpoints_step ON workflow_checkpoints(thread_id, step);



ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS alpaca_account_id TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS alpaca_mode TEXT DEFAULT 'trading';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS preferences JSONB DEFAULT '{}';
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS avatar_url TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS display_name TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- ===========================================================================
-- FUNCTIONS (service role executes these; anon/authenticated are revoked later)
-- ===========================================================================
-- Semantic memory retrieval with decay scoring
CREATE OR REPLACE FUNCTION retrieve_memory(
    p_user_id UUID,
    p_personality_id UUID,
    p_query_embedding vector(1536) DEFAULT NULL,
    p_ticker TEXT DEFAULT NULL,
    p_categories TEXT[] DEFAULT NULL,
    p_limit INT DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    layer memory_layer,
    category TEXT,
    ticker TEXT,
    content TEXT,
    importance FLOAT,
    metadata JSONB,
    created_at TIMESTAMPTZ,
    relevance_score FLOAT
)
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.layer,
        m.category,
        m.ticker,
        m.content,
        m.importance,
        m.metadata,
        m.created_at,
        -- Combined score: decay * importance * (optional) semantic similarity
        (
            m.importance *
            EXP(-0.693 * EXTRACT(EPOCH FROM (now() - m.created_at)) / 86400.0 /
                CASE m.layer
                    WHEN 'hot' THEN 1.0
                    WHEN 'warm' THEN 7.0
                    WHEN 'cold' THEN 90.0
                END
            ) *
            CASE
                WHEN p_query_embedding IS NOT NULL AND m.embedding IS NOT NULL
                THEN 1.0 - (m.embedding <=> p_query_embedding)  -- cosine similarity
                ELSE 1.0
            END
        )::FLOAT AS relevance_score
    FROM pilot_memory m
    WHERE m.user_id = p_user_id
      AND m.personality_id = p_personality_id
      AND (m.expires_at IS NULL OR m.expires_at > now())
      AND (p_ticker IS NULL OR m.ticker = p_ticker OR m.ticker IS NULL)
      AND (p_categories IS NULL OR m.category = ANY(p_categories))
    ORDER BY relevance_score DESC
    LIMIT p_limit;
END;
$$;

-- Cleanup expired memory entries (called by pg_cron)
CREATE OR REPLACE FUNCTION cleanup_expired_memory()
RETURNS INT
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM pilot_memory WHERE expires_at IS NOT NULL AND expires_at < now();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- Auto-promote high-importance warm memories to cold before expiry
CREATE OR REPLACE FUNCTION promote_warm_to_cold()
RETURNS INT
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    promoted_count INT;
BEGIN
    UPDATE pilot_memory
    SET layer = 'cold',
        expires_at = NULL,
        metadata = metadata || '{"promoted_from": "warm"}'::jsonb
    WHERE layer = 'warm'
      AND importance >= 0.75
      AND created_at < now() - INTERVAL '14 days'
      AND expires_at IS NOT NULL
      AND expires_at < now() + INTERVAL '7 days';
    GET DIAGNOSTICS promoted_count = ROW_COUNT;
    RETURN promoted_count;
END;
$$;


