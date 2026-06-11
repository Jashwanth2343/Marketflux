-- Conviction Ledger — Supabase Postgres migration.
-- The backend currently stores the ledger in MongoDB (conviction_ledger.py);
-- run this in the Supabase SQL editor when graduating the ledger to Postgres.
-- The module's public API is storage-agnostic, so the swap is an adapter
-- change, not a caller change.

create table if not exists ledger_theses (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  agent_id text not null default 'human',  -- keeps the agent-leaderboard option open
  ticker text not null,
  direction text not null check (direction in ('long', 'short')),
  source text not null default 'manual',   -- manual | copilot-auto
  status text not null default 'open' check (status in ('open', 'closed', 'invalidated')),
  entry_date date not null,
  entry_price numeric(14,4) not null,
  composite_score numeric(6,2),
  signal_label text,
  rationale text not null,
  price_target numeric(14,4),
  invalidation_price numeric(14,4),
  invalidation_date date,                  -- default: entry + 90 days (set by app)
  invalidation_score_floor numeric(6,2),
  invalidation_notes text default '',
  current_price numeric(14,4),
  unrealized_return_pct numeric(8,2),
  close_date date,
  close_price numeric(14,4),
  close_reason text,                       -- target | invalidation_price | expiry | manual
  return_pct numeric(8,2),
  benchmark_return_pct numeric(8,2),
  alpha_pp numeric(8,2),
  grade text check (grade in ('A','B','C','D','F')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists ledger_theses_user_status on ledger_theses (user_id, status, created_at desc);
create index if not exists ledger_theses_open_lookup on ledger_theses (user_id, agent_id, ticker, status);

create table if not exists ledger_audit (
  id bigint generated always as identity primary key,
  thesis_id uuid not null references ledger_theses (id),
  event text not null,
  detail jsonb not null default '{}',
  at timestamptz not null default now()
);

create index if not exists ledger_audit_thesis on ledger_audit (thesis_id, at);

create table if not exists ledger_daily_closes (
  symbol text not null,
  date date not null,
  close numeric(14,4) not null,
  primary key (symbol, date)
);

-- RLS: users see only their own theses; service role bypasses for grading.
alter table ledger_theses enable row level security;
alter table ledger_audit enable row level security;

create policy ledger_theses_own on ledger_theses
  for all using (auth.uid()::text = user_id);

create policy ledger_audit_own on ledger_audit
  for select using (
    exists (select 1 from ledger_theses t
            where t.id = ledger_audit.thesis_id
              and t.user_id = auth.uid()::text)
  );
