import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Sparkles, Pause, Play, RotateCcw, Plus, X,
  ChevronsRight, Briefcase, ShieldCheck, Activity, Newspaper,
  TrendingUp, TrendingDown, ChevronRight, Check, Loader2,
  Clock,
} from 'lucide-react';
import api from '@/lib/api';

/* =====================================================================
   AgentDetail — single-agent canvas matching the editorial-finance
   design system. 3-column bento:
     LEFT   ─ Positions · Risk guardrails · Market context
     CENTER ─ Plain-English strategy · Execution timeline
     RIGHT  ─ Related news · Strategy P&L (sparkline)

   Hooks into the existing /copilot/agents endpoint that
   StandingAgents already drives. Falls back to a representative
   demo payload when the backend isn't reachable so the surface is
   never empty.
   ===================================================================== */

const DEMO_AGENT = {
  id: 'demo',
  name: 'Idle cash sweep',
  instruction:
    'Sweep any cash over $20,000 from checking into my bond account.',
  category: 'Fund management',
  status: 'live',
  total_runs: 24,
  last_status: 'success',
};

const DEMO_POSITIONS = [
  { symbol: 'SPY',  qty: 120, price: 581.24,  change_pct: 6.05,  direction: 'up' },
  { symbol: 'NVDA', qty: 40,  price: 1182.40, change_pct: 25.79, direction: 'up' },
  { symbol: 'AAPL', qty: 80,  price: 185.22,  change_pct: -3.13, direction: 'down' },
  { symbol: 'XLP',  qty: 60,  price: 80.05,   change_pct: -2.85, direction: 'down' },
];

const DEMO_RISK = [
  { label: 'Max position size',  value: '$1,000' },
  { label: 'Daily loss limit',   value: '$2,500' },
  { label: 'Requires approval',  value: 'Off · auto-execute' },
  { label: 'Trading window',     value: 'RTH only' },
];

const DEMO_MACRO = [
  { ticker: 'VIX',   value: '29.49',    delta: 24.18, direction: 'up',   highlight: true },
  { ticker: 'SPX',   value: '5,874.20', delta: -0.62, direction: 'down' },
  { ticker: 'QQQ',   value: '504.18',   delta: -0.41, direction: 'down' },
  { ticker: 'DXY',   value: '104.82',   delta: 0.18,  direction: 'up' },
  { ticker: 'US10Y', value: '4.32%',    delta: 0.04,  direction: 'up' },
];

const DEMO_NEWS = [
  {
    sentiment: 'bullish',
    headline: 'Volatility spikes as Fed minutes signal caution',
    source: 'Reuters',
    timeAgo: '2m ago',
  },
  {
    sentiment: 'watch',
    headline: 'SPY options volume hits 3-month high into expiry',
    source: 'Bloomberg',
    timeAgo: '18m ago',
  },
];

const DEMO_STEPS = [
  {
    title: 'Monitor market conditions',
    detail: 'Polling every 60s',
    status: 'done',
    rows: [
      { kind: 'ok',   text: 'Connected to real-time feed' },
      { kind: 'ok',   text: 'Baseline snapshot captured' },
    ],
  },
  {
    title: 'Evaluate trigger condition',
    detail: 'VIX > 25',
    status: 'done',
    rows: [
      { kind: 'ok',   text: 'VIX 29.49 — condition met ✓' },
    ],
  },
  {
    title: 'Resolve instrument & size',
    detail: 'SPY 585P · $1,000 budget',
    status: 'done',
    rows: [
      { kind: 'data', text: 'Pulled options chain' },
      { kind: 'data', text: 'Selected 585P · ∆ -0.56' },
    ],
  },
  {
    title: 'Stage order for execution',
    detail: 'Limit @ mid · RTH only',
    status: 'running',
    rows: [
      { kind: 'ok', text: 'Pre-trade risk check passed' },
    ],
  },
  {
    title: 'Await fill & journal',
    detail: 'Pending approval',
    status: 'pending',
    rows: [],
  },
];

const DEMO_PNL = {
  realised: 2840,
  delta_pct: 6.4,
  spark: [1.0, 1.4, 1.1, 1.8, 2.0, 1.7, 2.3, 2.6, 2.2, 2.8, 2.9, 3.1, 3.0, 3.4],
};

function classNames(...x) { return x.filter(Boolean).join(' '); }

/* ───── Card primitives ───── */
function Card({ title, icon: Icon, actions, dismissable, onClose, children, className }) {
  return (
    <section
      className={classNames(
        'relative rounded-[12px] border border-border bg-card overflow-hidden',
        className,
      )}
      style={{ boxShadow: 'var(--mf-shadow-soft)' }}
    >
      {title && (
        <header className="flex items-center justify-between gap-2 px-4 py-3 border-b border-border/60">
          <div className="flex items-center gap-2 text-foreground">
            {Icon && <Icon className="w-4 h-4 text-muted-foreground" />}
            <span className="text-[13px] font-semibold tracking-tight">{title}</span>
          </div>
          <div className="flex items-center gap-1 text-muted-foreground">
            {actions}
            {dismissable && (
              <button
                onClick={onClose}
                className="inline-flex items-center justify-center w-6 h-6 rounded-md hover:bg-muted/60"
                aria-label="Hide"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
            <button className="inline-flex items-center justify-center w-6 h-6 rounded-md hover:bg-muted/60" aria-label="Expand">
              <ChevronsRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

function Delta({ value, direction }) {
  const positive = direction === 'up';
  const Arrow = positive ? TrendingUp : TrendingDown;
  return (
    <span
      className={classNames(
        'inline-flex items-center gap-1 font-mono text-[12px] tabular-nums',
        positive ? 'mf-bull' : 'mf-bear',
      )}
    >
      <Arrow className="w-3 h-3" />
      {positive ? '+' : ''}
      {value.toFixed(2)}%
    </span>
  );
}

/* ───── Cards ───── */
function PositionsCard({ rows, onClose }) {
  return (
    <Card title="Positions" icon={Briefcase} dismissable onClose={onClose}>
      <ul className="flex flex-col gap-3">
        {rows.map((r) => (
          <li key={r.symbol} className="grid grid-cols-[1fr_auto_auto] items-center gap-4">
            <div className="min-w-0">
              <div className="text-[13px] font-semibold tracking-tight text-foreground">{r.symbol}</div>
              <div className="text-[11px] text-muted-foreground font-mono">{r.qty} sh</div>
            </div>
            <div className="font-mono text-[13px] tabular-nums text-foreground text-right">
              ${r.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-right"><Delta value={r.change_pct} direction={r.direction} /></div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function RiskCard({ rows, onClose }) {
  return (
    <Card title="Risk guardrails" icon={ShieldCheck} dismissable onClose={onClose}>
      <ul className="flex flex-col gap-2">
        {rows.map((r) => (
          <li key={r.label} className="flex items-start gap-2 text-[12.5px]">
            <Check className="w-3.5 h-3.5 mt-[3px] text-[color:var(--mf-bull-strong)] flex-shrink-0" />
            <span className="flex-1 text-muted-foreground">{r.label}</span>
            <span className="font-mono text-foreground tabular-nums">{r.value}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function MarketContextCard({ rows, onClose }) {
  return (
    <Card title="Market context" icon={Activity} dismissable onClose={onClose}>
      <ul className="flex flex-col">
        {rows.map((r) => (
          <li
            key={r.ticker}
            className={classNames(
              'grid grid-cols-[60px_1fr_auto] items-center gap-3 py-2 px-2 -mx-2 rounded-md',
              r.highlight && 'bg-[color:var(--mf-accent-bg)]',
            )}
          >
            <div
              className={classNames(
                'text-[12.5px] font-semibold tracking-tight',
                r.highlight ? 'text-[color:var(--mf-accent-strong)]' : 'text-foreground',
              )}
            >
              {r.ticker}
            </div>
            <div className="font-mono text-[13px] tabular-nums text-foreground text-right">{r.value}</div>
            <Delta value={r.delta} direction={r.direction} />
          </li>
        ))}
      </ul>
    </Card>
  );
}

function StrategyCard({ agent }) {
  return (
    <section
      className="relative rounded-[18px] border border-border bg-card overflow-hidden"
      style={{
        boxShadow: 'var(--mf-shadow-soft)',
        background:
          'radial-gradient(ellipse 90% 60% at 10% 0%, var(--mf-accent-bg) 0%, transparent 65%), hsl(var(--card))',
      }}
    >
      {/* Top kicker + status */}
      <header className="flex items-center justify-between gap-3 px-6 pt-5">
        <span className="text-[10.5px] font-medium tracking-[0.18em] uppercase text-muted-foreground">
          Plain-English strategy
        </span>
        <span
          className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10.5px] font-medium"
          style={{
            background: 'var(--mf-accent-bg)',
            color: 'var(--mf-accent-strong)',
            borderColor: 'var(--mf-accent-border)',
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: 'var(--mf-accent-strong)', boxShadow: '0 0 8px var(--mf-accent-glow)' }}
          />
          FluxAI · compiled
        </span>
      </header>

      {/* Quote */}
      <div className="px-6 pt-3 pb-5">
        <p
          className="text-[26px] md:text-[30px] leading-[1.2] text-foreground"
          style={{ fontFamily: 'var(--mf-font-serif)' }}
        >
          &ldquo;{agent.instruction}&rdquo;
        </p>
        <div className="mt-5">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/40 px-3 py-1 text-[11.5px] font-medium text-muted-foreground">
            {agent.category || 'Strategy'}
          </span>
        </div>
      </div>
    </section>
  );
}

function StepIcon({ status }) {
  if (status === 'done') {
    return (
      <span
        className="inline-flex items-center justify-center w-6 h-6 rounded-full border-2"
        style={{ borderColor: 'var(--mf-accent)', color: 'var(--mf-accent-strong)' }}
      >
        <Check className="w-3.5 h-3.5" strokeWidth={3} />
      </span>
    );
  }
  if (status === 'running') {
    return (
      <span
        className="inline-flex items-center justify-center w-6 h-6 rounded-full border-2"
        style={{ borderColor: 'var(--mf-accent)' }}
      >
        <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: 'var(--mf-accent)' }} />
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center justify-center w-6 h-6 rounded-full border-2 border-dashed"
      style={{ borderColor: 'var(--mf-border-strong)' }}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50" />
    </span>
  );
}

function ExecutionTimeline({ steps }) {
  const totalDone = steps.filter((s) => s.status === 'done' || s.status === 'running').length;
  return (
    <Card
      title="Execution timeline"
      icon={Activity}
      actions={
        <span className="text-[10.5px] font-mono tracking-[0.18em] uppercase text-muted-foreground">
          {totalDone}/{steps.length} steps
        </span>
      }
    >
      <ol className="relative flex flex-col gap-5">
        {steps.map((s, i) => {
          const isLast = i === steps.length - 1;
          return (
            <li key={s.title} className="relative pl-9">
              {/* connector */}
              {!isLast && (
                <span
                  aria-hidden
                  className="absolute left-[11px] top-7 bottom-[-20px] w-px"
                  style={{ background: 'var(--mf-border)' }}
                />
              )}
              <span className="absolute left-0 top-0"><StepIcon status={s.status} /></span>

              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-[13.5px] font-semibold tracking-tight text-foreground">{s.title}</span>
                {s.status === 'running' && (
                  <span
                    className="text-[10px] font-mono tracking-[0.18em] uppercase"
                    style={{ color: 'var(--mf-accent-strong)' }}
                  >
                    RUNNING
                  </span>
                )}
              </div>
              {s.detail && <div className="mt-0.5 text-[12px] text-muted-foreground">{s.detail}</div>}

              {s.rows.length > 0 && (
                <div className="mt-2 flex flex-col gap-1">
                  {s.rows.map((r, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-2 rounded-md border border-border/70 bg-muted/30 px-3 py-1.5 font-mono text-[11.5px] text-muted-foreground"
                    >
                      <ChevronRight className="w-3 h-3 flex-shrink-0" />
                      <span className="flex-1 truncate">{r.text}</span>
                    </div>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

function NewsCard({ items, onClose }) {
  return (
    <Card title="Related news" icon={Newspaper} dismissable onClose={onClose}>
      <ul className="flex flex-col gap-2.5">
        {items.map((n, i) => {
          const isBullish = n.sentiment === 'bullish';
          const tone = isBullish
            ? { bg: 'var(--mf-bull-bg)', border: 'var(--mf-bull-border)', color: 'var(--mf-bull-strong)', label: 'BULLISH' }
            : { bg: 'var(--mf-accent-bg)', border: 'var(--mf-accent-border)', color: 'var(--mf-accent-strong)', label: 'WATCH' };
          return (
            <li
              key={i}
              className="rounded-md border border-border bg-muted/20 px-3 py-2.5 flex flex-col gap-1.5"
            >
              <span
                className="inline-flex items-center gap-1 self-start rounded-sm border px-1.5 py-0.5 text-[10px] font-semibold tracking-[0.14em]"
                style={{ background: tone.bg, color: tone.color, borderColor: tone.border }}
              >
                {tone.label}
              </span>
              <div className="text-[12.5px] leading-snug text-foreground">{n.headline}</div>
              <div className="flex items-center justify-between text-[10.5px] font-mono text-muted-foreground">
                <span>{n.source}</span>
                <span>{n.timeAgo}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function Sparkline({ data, color }) {
  const w = 220;
  const h = 60;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = w / (data.length - 1);
  const points = data.map((v, i) => `${i * stepX},${h - ((v - min) / range) * (h - 8) - 4}`).join(' ');
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-[60px]">
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function PnlCard({ pnl, onClose }) {
  return (
    <Card title="Strategy P&L" icon={TrendingUp} dismissable onClose={onClose}>
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-[10.5px] tracking-[0.18em] uppercase text-muted-foreground font-mono">REALISED · LAST 30 SESSIONS</span>
        </div>
        <div className="flex items-baseline gap-3">
          <span className="font-mono tabular-nums text-[28px] font-semibold mf-bull">
            +${pnl.realised.toLocaleString()}
          </span>
          <Delta value={pnl.delta_pct} direction="up" />
        </div>
        <Sparkline data={pnl.spark} color="var(--mf-bull)" />
      </div>
    </Card>
  );
}

/* ───── Main page ───── */
export default function AgentDetail() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState(null);
  const [paused, setPaused] = useState(false);
  const [hidden, setHidden] = useState({});

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!agentId || agentId === 'demo') { setAgent(DEMO_AGENT); return; }
      try {
        const { data } = await api.get(`/copilot/agents`);
        const found = (data?.items || []).find((a) => a.id === agentId);
        if (!cancelled) {
          setAgent(found ? {
            id: found.id,
            name: found.name || 'Agent',
            instruction: found.instruction || DEMO_AGENT.instruction,
            category: found.category || 'Strategy',
            status: found.status || 'idle',
            total_runs: found.run_count ?? 0,
          } : DEMO_AGENT);
        }
      } catch {
        if (!cancelled) setAgent(DEMO_AGENT);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [agentId]);

  const heroAgent = agent || DEMO_AGENT;
  const isLive = !paused && (heroAgent.status === 'live' || heroAgent.status === 'running' || agentId === 'demo');

  const hide = (key) => setHidden((h) => ({ ...h, [key]: true }));

  return (
    <div
      className="min-h-full w-full text-foreground"
      style={{
        background:
          'radial-gradient(ellipse 60% 50% at 18% 0%, var(--mf-accent-bg) 0%, transparent 60%), radial-gradient(ellipse 50% 40% at 90% 100%, var(--mf-bull-bg) 0%, transparent 60%), hsl(var(--background))',
      }}
      data-testid="agent-detail-page"
    >
      {/* Header strip */}
      <div className="px-6 pt-6 pb-4">
        <div className="flex flex-wrap items-center gap-3 justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/copilot?tab=proposals')}
              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/30 px-2.5 py-1.5 text-[12px] text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Agents
            </button>
            <span
              className="inline-flex items-center justify-center w-9 h-9 rounded-full"
              style={{ background: 'var(--mf-accent-bg)', border: '1px solid var(--mf-accent-border)' }}
            >
              <Sparkles className="w-4 h-4" style={{ color: 'var(--mf-accent-strong)' }} />
            </span>
            <div className="flex flex-col">
              <h1 className="text-[22px] md:text-[26px] font-semibold tracking-tight text-foreground leading-tight">
                {heroAgent.name}
              </h1>
              <div className="flex items-center gap-2 text-[11.5px] text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">
                  <span
                    className={classNames(
                      'w-1.5 h-1.5 rounded-full',
                      isLive ? 'pulse-live' : '',
                    )}
                    style={{ background: isLive ? 'var(--mf-bull)' : 'var(--mf-fg-tertiary)' }}
                  />
                  {isLive ? 'Executing live' : 'Paused'}
                </span>
                <span aria-hidden>·</span>
                <span className="font-mono tabular-nums">{heroAgent.total_runs ?? 0} total runs</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setPaused((p) => !p)}
              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/30 px-3 py-1.5 text-[12px] font-medium text-foreground hover:bg-muted/60 transition-colors"
            >
              {paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
              {paused ? 'Resume' : 'Pause'}
            </button>
            <button
              className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-semibold transition-colors"
              style={{
                background: 'var(--mf-accent-bg)',
                color: 'var(--mf-accent-strong)',
                border: '1px solid var(--mf-accent-border)',
              }}
            >
              <RotateCcw className="w-3.5 h-3.5" /> Re-run
            </button>
            <button
              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/30 px-3 py-1.5 text-[12px] font-medium text-foreground hover:bg-muted/60 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" /> Add widget
            </button>
          </div>
        </div>
      </div>

      {/* 3-column bento */}
      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr_320px] gap-4 px-6 pb-12">
        {/* LEFT */}
        <div className="flex flex-col gap-4 min-w-0">
          {!hidden.positions && <PositionsCard rows={DEMO_POSITIONS} onClose={() => hide('positions')} />}
          {!hidden.risk      && <RiskCard rows={DEMO_RISK} onClose={() => hide('risk')} />}
          {!hidden.macro     && <MarketContextCard rows={DEMO_MACRO} onClose={() => hide('macro')} />}
        </div>

        {/* CENTER */}
        <div className="flex flex-col gap-4 min-w-0">
          <StrategyCard agent={heroAgent} />
          <ExecutionTimeline steps={DEMO_STEPS} />
        </div>

        {/* RIGHT */}
        <div className="flex flex-col gap-4 min-w-0">
          {!hidden.news && <NewsCard items={DEMO_NEWS} onClose={() => hide('news')} />}
          {!hidden.pnl  && <PnlCard pnl={DEMO_PNL} onClose={() => hide('pnl')} />}
        </div>
      </div>
    </div>
  );
}
