-- Copilot trust-path tables (Supabase Postgres).
-- Replaces the legacy Mongo collections: copilot_pending_trades,
-- copilot_messages, copilot_trade_log. Idempotent — applied at startup.

CREATE TABLE IF NOT EXISTS copilot_pending_trades (
    id          UUID PRIMARY KEY,
    user_id     TEXT NOT NULL,
    tool        TEXT NOT NULL,
    args        JSONB NOT NULL DEFAULT '{}'::jsonb,
    preview     JSONB NOT NULL DEFAULT '{}'::jsonb,
    status      TEXT NOT NULL DEFAULT 'pending',
    result      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    executed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_cpt_user_status ON copilot_pending_trades (user_id, status);
CREATE INDEX IF NOT EXISTS idx_cpt_created    ON copilot_pending_trades (created_at);

CREATE TABLE IF NOT EXISTS copilot_messages (
    id         BIGSERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL,
    session_id TEXT,
    message    TEXT NOT NULL,
    response   TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cm_user_session ON copilot_messages (user_id, session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cm_user_created ON copilot_messages (user_id, created_at);

CREATE TABLE IF NOT EXISTS copilot_trade_log (
    id      BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    ts      TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_ctl_user_ts ON copilot_trade_log (user_id, ts DESC);
