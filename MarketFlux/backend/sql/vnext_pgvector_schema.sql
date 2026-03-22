CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS daily_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_date DATE NOT NULL,
    owner_user_id TEXT,
    macro_regime JSONB NOT NULL,
    top_signals JSONB NOT NULL DEFAULT '[]'::jsonb,
    watchlist_updates JSONB NOT NULL DEFAULT '[]'::jsonb,
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (brief_date, owner_user_id)
);

CREATE TABLE IF NOT EXISTS research_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id TEXT,
    scope TEXT NOT NULL,
    ticker TEXT,
    prompt TEXT,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    output JSONB NOT NULL,
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    model_cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS signal_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_type TEXT NOT NULL,
    asset_scope TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    tickers TEXT[] NOT NULL DEFAULT '{}',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    freshness TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ticker_workspaces (
    ticker TEXT PRIMARY KEY,
    snapshot JSONB NOT NULL,
    thesis JSONB NOT NULL,
    filings JSONB NOT NULL,
    transcripts JSONB NOT NULL,
    insider JSONB NOT NULL,
    macro_context JSONB NOT NULL,
    technicals JSONB NOT NULL,
    open_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saved_theses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    thesis_text TEXT NOT NULL,
    stance TEXT NOT NULL,
    confidence INTEGER NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    catalysts JSONB NOT NULL DEFAULT '[]'::jsonb,
    risks JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id TEXT NOT NULL,
    watchlist_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal',
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    catalyst_dates JSONB NOT NULL DEFAULT '[]'::jsonb,
    alert_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
    thesis_id UUID REFERENCES saved_theses(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS competitor_profiles (
    slug TEXT PRIMARY KEY,
    audience TEXT NOT NULL,
    strengths JSONB NOT NULL DEFAULT '[]'::jsonb,
    weaknesses JSONB NOT NULL DEFAULT '[]'::jsonb,
    pricing_notes JSONB NOT NULL DEFAULT '[]'::jsonb,
    proof_points JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS terminal_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id TEXT NOT NULL,
    session_key TEXT NOT NULL UNIQUE,
    objective TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'paper',
    risk_profile TEXT NOT NULL DEFAULT 'balanced',
    capital_base NUMERIC(18, 2) NOT NULL DEFAULT 100000,
    status TEXT NOT NULL DEFAULT 'running',
    request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS strategy_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id TEXT NOT NULL,
    session_id UUID REFERENCES terminal_sessions(id) ON DELETE CASCADE,
    strategy_type TEXT NOT NULL,
    ticker TEXT,
    tickers TEXT[] NOT NULL DEFAULT '{}',
    title TEXT NOT NULL,
    thesis TEXT NOT NULL,
    entry TEXT,
    target TEXT,
    stop TEXT,
    confidence INTEGER NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    invalidation TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    competing_view JSONB NOT NULL DEFAULT '[]'::jsonb,
    market_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_trace JSONB NOT NULL DEFAULT '{}'::jsonb,
    usage JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_paper BOOLEAN NOT NULL DEFAULT TRUE,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    execution_status TEXT NOT NULL DEFAULT 'pending_approval',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (is_paper = TRUE OR approved_by IS NOT NULL),
    CHECK (execution_status IN ('pending_approval', 'approved', 'rejected', 'paper_open', 'paper_closed', 'blocked'))
);

CREATE TABLE IF NOT EXISTS execution_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES strategy_proposals(id) ON DELETE CASCADE,
    owner_user_id TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decision TEXT NOT NULL DEFAULT 'approved',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id TEXT NOT NULL,
    strategy_id UUID NOT NULL REFERENCES strategy_proposals(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity NUMERIC(18, 4) NOT NULL,
    order_type TEXT NOT NULL DEFAULT 'market',
    limit_price NUMERIC(18, 4),
    stop_price NUMERIC(18, 4),
    broker_status TEXT NOT NULL DEFAULT 'queued',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_paper BOOLEAN NOT NULL DEFAULT TRUE,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    execution_status TEXT NOT NULL DEFAULT 'pending_approval',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (is_paper = TRUE OR approved_by IS NOT NULL),
    CHECK (execution_status IN ('pending_approval', 'approved', 'rejected', 'queued', 'submitted', 'filled', 'cancelled', 'blocked'))
);

CREATE TABLE IF NOT EXISTS paper_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id TEXT NOT NULL,
    strategy_id UUID REFERENCES strategy_proposals(id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    quantity NUMERIC(18, 4) NOT NULL DEFAULT 0,
    avg_price NUMERIC(18, 4) NOT NULL DEFAULT 0,
    mark_price NUMERIC(18, 4) NOT NULL DEFAULT 0,
    unrealized_pnl NUMERIC(18, 4) NOT NULL DEFAULT 0,
    opened_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_paper BOOLEAN NOT NULL DEFAULT TRUE,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    execution_status TEXT NOT NULL DEFAULT 'pending_approval',
    CHECK (is_paper = TRUE OR approved_by IS NOT NULL),
    CHECK (execution_status IN ('pending_approval', 'approved', 'open', 'closed', 'blocked'))
);

CREATE TABLE IF NOT EXISTS model_usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES terminal_sessions(id) ON DELETE SET NULL,
    owner_user_id TEXT,
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    request_purpose TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost_usd NUMERIC(12, 6),
    raw_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS research_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker TEXT,
    source_type TEXT NOT NULL,
    source_url TEXT,
    title TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_briefs_date ON daily_briefs (brief_date DESC);
CREATE INDEX IF NOT EXISTS idx_research_runs_owner_created ON research_runs (owner_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signal_events_created ON signal_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_saved_theses_owner_ticker ON saved_theses (owner_user_id, ticker, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_watchlist_items_owner_watchlist ON watchlist_items (owner_user_id, watchlist_id, ticker);
CREATE INDEX IF NOT EXISTS idx_terminal_sessions_owner_created ON terminal_sessions (owner_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_proposals_owner_created ON strategy_proposals (owner_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_proposals_session_created ON strategy_proposals (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_approvals_strategy_created ON execution_approvals (strategy_id, approved_at DESC);
CREATE INDEX IF NOT EXISTS idx_paper_orders_strategy_created ON paper_orders (strategy_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_paper_positions_owner_symbol ON paper_positions (owner_user_id, symbol);
CREATE INDEX IF NOT EXISTS idx_model_usage_events_session_created ON model_usage_events (session_id, created_at DESC);
