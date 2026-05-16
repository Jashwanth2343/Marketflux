CREATE TABLE IF NOT EXISTS backtest_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id TEXT NOT NULL,
    strategy_dsl JSONB NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    capital NUMERIC(18, 2) NOT NULL,
    cost_model JSONB NOT NULL DEFAULT '{}'::jsonb,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    equity_curve JSONB NOT NULL DEFAULT '[]'::jsonb,
    trades JSONB NOT NULL DEFAULT '[]'::jsonb,
    walk_forward_windows JSONB,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('running', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_owner_created ON backtest_runs (owner_user_id, created_at DESC);
