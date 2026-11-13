-- Conviction ledger tables. Canonical copy of the former docs/migrations/ledger.sql.
-- Policies are in 20261112000003_enable_rls.sql.

CREATE TABLE IF NOT EXISTS ledger_theses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  agent_id TEXT NOT NULL DEFAULT 'human',
  ticker TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
  source TEXT NOT NULL DEFAULT 'manual',
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'invalidated')),
  entry_date DATE NOT NULL,
  entry_price NUMERIC(14,4) NOT NULL,
  composite_score NUMERIC(6,2),
  signal_label TEXT,
  rationale TEXT NOT NULL,
  price_target NUMERIC(14,4),
  invalidation_price NUMERIC(14,4),
  invalidation_date DATE,
  invalidation_score_floor NUMERIC(6,2),
  invalidation_notes TEXT DEFAULT '',
  current_price NUMERIC(14,4),
  unrealized_return_pct NUMERIC(8,2),
  close_date DATE,
  close_price NUMERIC(14,4),
  close_reason TEXT,
  return_pct NUMERIC(8,2),
  benchmark_return_pct NUMERIC(8,2),
  alpha_pp NUMERIC(8,2),
  grade TEXT CHECK (grade IN ('A','B','C','D','F')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ledger_theses_user_status ON ledger_theses (user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS ledger_theses_open_lookup ON ledger_theses (user_id, agent_id, ticker, status);

CREATE TABLE IF NOT EXISTS ledger_audit (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  thesis_id UUID NOT NULL REFERENCES ledger_theses (id),
  event TEXT NOT NULL,
  detail JSONB NOT NULL DEFAULT '{}',
  at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ledger_audit_thesis ON ledger_audit (thesis_id, at);

CREATE TABLE IF NOT EXISTS ledger_daily_closes (
  symbol TEXT NOT NULL,
  date DATE NOT NULL,
  close NUMERIC(14,4) NOT NULL,
  PRIMARY KEY (symbol, date)
);
