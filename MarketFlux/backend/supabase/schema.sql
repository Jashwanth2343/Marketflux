-- ===========================================================================
-- MarketFlux Supabase Schema
-- Primary brain: auth, copilot, memory (pgvector), portfolio tracking
-- Run via Supabase SQL Editor or supabase db push
-- ===========================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector for semantic memory
CREATE EXTENSION IF NOT EXISTS pg_cron;      -- scheduled cleanup jobs
CREATE EXTENSION IF NOT EXISTS moddatetime;  -- auto-update updated_at

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

CREATE TRIGGER profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

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

CREATE TRIGGER personalities_updated_at
    BEFORE UPDATE ON personalities
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

CREATE INDEX idx_personalities_user ON personalities(user_id);
CREATE INDEX idx_personalities_slug ON personalities(slug);

-- ===========================================================================
-- TRADE PROPOSALS (the core copilot artifact)
-- ===========================================================================
CREATE TYPE proposal_status AS ENUM (
    'pending', 'approved', 'rejected', 'executed', 'failed', 'expired'
);

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

CREATE TRIGGER proposals_updated_at
    BEFORE UPDATE ON trade_proposals
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

CREATE INDEX idx_proposals_user ON trade_proposals(user_id);
CREATE INDEX idx_proposals_personality ON trade_proposals(personality_id);
CREATE INDEX idx_proposals_status ON trade_proposals(status);
CREATE INDEX idx_proposals_ticker ON trade_proposals(ticker);
CREATE INDEX idx_proposals_created ON trade_proposals(created_at DESC);

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

CREATE INDEX idx_audit_proposal ON audit_events(proposal_id);
CREATE INDEX idx_audit_created ON audit_events(created_at DESC);

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

CREATE INDEX idx_activity_personality ON activity_events(personality_id);
CREATE INDEX idx_activity_created ON activity_events(created_at DESC);

-- ===========================================================================
-- PILOT MEMORY (layered institutional knowledge with pgvector)
-- ===========================================================================
CREATE TYPE memory_layer AS ENUM ('hot', 'warm', 'cold');

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

CREATE INDEX idx_memory_user_personality ON pilot_memory(user_id, personality_id);
CREATE INDEX idx_memory_layer ON pilot_memory(layer);
CREATE INDEX idx_memory_ticker ON pilot_memory(ticker);
CREATE INDEX idx_memory_category ON pilot_memory(category);
CREATE INDEX idx_memory_expires ON pilot_memory(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_memory_created ON pilot_memory(created_at DESC);

-- HNSW index for fast vector similarity search
CREATE INDEX idx_memory_embedding ON pilot_memory
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

CREATE INDEX idx_journal_personality ON journal_entries(personality_id);

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

CREATE INDEX idx_drift_personality ON drift_flags(personality_id);

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

CREATE INDEX idx_snapshots_user ON portfolio_snapshots(user_id, snapshot_date DESC);

-- ===========================================================================
-- ROW LEVEL SECURITY
-- ===========================================================================

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_consent ENABLE ROW LEVEL SECURITY;
ALTER TABLE personalities ENABLE ROW LEVEL SECURITY;
ALTER TABLE trade_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE pilot_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE drift_flags ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_snapshots ENABLE ROW LEVEL SECURITY;

-- Profiles: users see only their own
CREATE POLICY profiles_self ON profiles
    FOR ALL USING (id = auth.uid());

-- Consent: users see only their own
CREATE POLICY consent_self ON user_consent
    FOR ALL USING (user_id = auth.uid());

-- Personalities: see your own + public seeds
CREATE POLICY personalities_read ON personalities
    FOR SELECT USING (user_id = auth.uid() OR is_seed = true OR public = true);
CREATE POLICY personalities_write ON personalities
    FOR ALL USING (user_id = auth.uid());

-- Proposals: users see only their own
CREATE POLICY proposals_self ON trade_proposals
    FOR ALL USING (user_id = auth.uid());

-- Audit: users see events for their proposals
CREATE POLICY audit_self ON audit_events
    FOR SELECT USING (user_id = auth.uid());

-- Activity: users see events for personalities they can access
CREATE POLICY activity_read ON activity_events
    FOR SELECT USING (user_id = auth.uid());

-- Memory: users see only their own
CREATE POLICY memory_self ON pilot_memory
    FOR ALL USING (user_id = auth.uid());

-- Journal: readable if personality is public or yours
CREATE POLICY journal_read ON journal_entries
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM personalities p
            WHERE p.id = journal_entries.personality_id
            AND (p.user_id = auth.uid() OR p.public = true OR p.is_seed = true)
        )
    );

-- Drift: users see their own personality's flags
CREATE POLICY drift_self ON drift_flags
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM personalities p
            WHERE p.id = drift_flags.personality_id
            AND p.user_id = auth.uid()
        )
    );

-- Snapshots: users see only their own
CREATE POLICY snapshots_self ON portfolio_snapshots
    FOR ALL USING (user_id = auth.uid());

-- ===========================================================================
-- FUNCTIONS
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

-- Schedule cleanup (every hour) and promotion (daily at 3am UTC)
-- NOTE: pg_cron may need to be enabled via Supabase dashboard > Database > Extensions
-- SELECT cron.schedule('cleanup-expired-memory', '0 * * * *', 'SELECT cleanup_expired_memory()');
-- SELECT cron.schedule('promote-warm-memory', '0 3 * * *', 'SELECT promote_warm_to_cold()');

-- ===========================================================================
-- SEED DATA: auto-create profile on signup
-- ===========================================================================
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    INSERT INTO profiles (id, email, display_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1))
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();
