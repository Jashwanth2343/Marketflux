import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
    Plane, Send, Loader2, Brain, Wrench, CheckCircle2, AlertTriangle,
    ArrowUpCircle, ArrowDownCircle, XCircle, ShieldCheck, Square,
    Shield, Zap, Cpu, ChevronDown, History,
    ShieldAlert, ShieldX, Gauge, FlaskConical, BarChart3, Crosshair,
    Users, GraduationCap, Award, Compass, Calculator, Swords,
    TrendingUp, TrendingDown, CalendarClock, Slash, BookMarked,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { API_BASE } from '@/lib/api';
import api from '@/lib/api';
import CopilotMemory from '@/components/copilot/CopilotMemory';
import RichMarkdown from '@/components/RichMarkdown';

// Three curated "starter" cards for the empty/landing state.
const HERO_CARDS = [
    { icon: Gauge, title: 'Score & size a name', sub: 'Quant conviction + risk-based sizing',
      prompt: 'Score NVDA on your 20-signal model and size it to its risk' },
    { icon: Users, title: 'Convene the research team', sub: '5 analysts in parallel → a verdict',
      prompt: 'Convene the research team on NVDA, then give me your verdict' },
    { icon: GraduationCap, title: 'Review & learn', sub: 'Grade my book, learn from outcomes',
      prompt: 'Review my track record and tell me what to learn from it' },
];

// Quick-prompt chips shown under the composer.
const SUGGESTIONS = [
    'Run a portfolio risk X-ray and show my crash exposure',
    'Backtest an RSI dip-buy on AAPL & MSFT over the last 3 years',
    'Rank AMD, AVGO, MU, INTC by conviction and buy the best',
    'What should I trim or add right now?',
];

// Slash commands — power-user shortcuts. `stub` fills the box for a ticker;
// `prompt` fires immediately.
const SLASH = [
    { cmd: '/debate', icon: Swords, desc: 'Bull vs Bear committee + verdict', stub: 'Bull vs Bear debate, then your verdict, on: ' },
    { cmd: '/regime', icon: Compass, desc: 'Read the tape & how to position', prompt: 'What market regime are we in and how should I position?' },
    { cmd: '/whatif', icon: Calculator, desc: 'Simulate a trade’s portfolio impact', stub: 'Simulate the portfolio impact of buying: ' },
    { cmd: '/score', icon: Gauge, desc: 'Quant conviction score + sizing', stub: 'Score and risk-size: ' },
    { cmd: '/research', icon: Users, desc: 'Convene the 5-analyst team', stub: 'Convene the research team, then a verdict, on: ' },
    { cmd: '/earnings', icon: CalendarClock, desc: 'Earnings catalyst intel', stub: 'Earnings catalyst risk for: ' },
    { cmd: '/risk', icon: Shield, desc: 'Portfolio risk X-ray', prompt: 'Run a portfolio risk X-ray and show my crash exposure' },
    { cmd: '/backtest', icon: FlaskConical, desc: 'Backtest a strategy idea', stub: 'Backtest this strategy idea: ' },
    { cmd: '/review', icon: GraduationCap, desc: 'Review my record & learn', prompt: 'Review my track record and tell me what to learn from it' },
];

let _mid = 0;
const nextId = () => `m${Date.now()}_${_mid++}`;

// ===========================================================================
// Activity renderers — thinking lines, collapsible tool pills, result cards
// ===========================================================================

function ThinkingRow({ text }) {
    return (
        <div className="flex items-start gap-2.5 text-[13px] text-muted-foreground animate-in fade-in duration-300">
            <Brain className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-primary/70" />
            <span className="leading-relaxed">{text}</span>
        </div>
    );
}

// Composer-style collapsible status pill with an elapsed-time badge.
function ToolPill({ item }) {
    const [open, setOpen] = useState(false);
    const done = item.status != null;
    const failed = done && item.ok === false;
    const code = item.name === 'run_python' ? item.args?.code : null;
    const hasDetail = !!code || (done && !!item.summary);
    const elapsed = item.elapsed != null ? `${item.elapsed}s` : null;
    return (
        <div className={`overflow-hidden rounded-xl border transition-colors animate-in fade-in slide-in-from-left-1 duration-300 ${
            item.is_trade ? 'border-primary/30 bg-primary/[0.06]' : 'border-border bg-card'
        }`}>
            <button
                type="button"
                onClick={() => hasDetail && setOpen((o) => !o)}
                className={`flex w-full items-center gap-2.5 px-3 py-2 text-left ${hasDetail ? 'cursor-pointer' : 'cursor-default'}`}
            >
                <span className="flex-shrink-0">
                    {!done ? <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                        : failed ? <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                            : <CheckCircle2 className="h-3.5 w-3.5 text-primary" />}
                </span>
                <span className="flex min-w-0 flex-1 items-center gap-1.5">
                    {item.is_trade && <Wrench className="h-3 w-3 flex-shrink-0 text-primary" />}
                    <span className="truncate text-[13px] font-medium text-foreground/90">
                        {item.label}{!done ? '…' : ''}
                    </span>
                </span>
                {elapsed && <span className="flex-shrink-0 font-mono text-[11px] text-muted-foreground">{elapsed}</span>}
                {hasDetail && (
                    <ChevronDown className={`h-3.5 w-3.5 flex-shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
                )}
            </button>
            {open && hasDetail && (
                <div className="border-t border-border px-3 py-2">
                    {code && (
                        <pre className="mb-1.5 overflow-x-auto rounded-lg border border-border bg-muted/60 px-3 py-2 font-mono text-[11px] leading-relaxed text-foreground/90 whitespace-pre-wrap">
                            {code}
                        </pre>
                    )}
                    {done && item.summary && (
                        <div className={`font-mono text-[11px] ${failed ? 'text-amber-500' : 'text-muted-foreground'}`}>
                            → {item.summary}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

function TradeCard({ t, onAction }) {
    const buy = t.side === 'buy';
    const isCancel = t.action === 'cancel_all';
    const Icon = isCancel ? XCircle : buy ? ArrowUpCircle : ArrowDownCircle;
    const pending = t.pending && !t.resolved;
    const rejected = t.resolved === 'rejected';
    const tone = rejected || isCancel ? 'text-muted-foreground border-border'
        : buy ? 'text-primary border-primary/40 bg-primary/[0.05]'
            : 'text-amber-500 border-amber-500/40 bg-amber-500/[0.05]';
    const acted = t.resolved === 'executed' || (!t.pending);
    const verb = isCancel ? (acted ? 'Cancelled all open orders' : 'Cancel all open orders')
        : t.action === 'close' ? `${acted ? 'Closed' : 'Close'} ${t.symbol}`
            : `${acted ? (buy ? 'Bought' : 'Sold') : (buy ? 'Buy' : 'Sell')} ${t.qty} ${t.symbol}`;
    const badge = rejected ? 'rejected'
        : t.resolved === 'executed' ? (t.status || 'executed')
            : pending ? 'needs approval' : t.status;
    return (
        <div className={`rounded-xl border px-3.5 py-2.5 animate-in fade-in zoom-in-95 duration-300 ${tone}`}>
            <div className="flex items-center gap-3">
                <Icon className="h-5 w-5 flex-shrink-0" />
                <div className="flex-1 font-mono text-sm">
                    <span className="font-semibold tracking-tight">{verb}</span>
                    {t.order_type === 'limit' && t.limit_price ? <span className="ml-2 opacity-80">@ ${t.limit_price}</span> : null}
                    {t.price && <span className="ml-2 opacity-80">@ ${t.price}</span>}
                    {badge && <span className="ml-2 rounded-full bg-foreground/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wider opacity-80">{badge}</span>}
                </div>
            </div>
            {pending && (
                <div className="mt-2.5 flex gap-2">
                    <Button size="sm" onClick={() => onAction?.(t.proposal_id, 'approve')} disabled={!!t.resolving}
                        className="h-8 flex-1 gap-1.5 rounded-lg">
                        {t.resolving === 'approve' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />} Approve
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => onAction?.(t.proposal_id, 'reject')} disabled={!!t.resolving}
                        className="h-8 gap-1.5 rounded-lg">
                        <XCircle className="h-3.5 w-3.5" /> Reject
                    </Button>
                </div>
            )}
        </div>
    );
}

// --- conviction-ledger capture (design-doc path b: one-click log) ----------
function LogThesisButton({ message }) {
    const [state, setState] = useState('idle'); // idle | form | saving | done
    const [ticker, setTicker] = useState('');
    const [direction, setDirection] = useState('long');

    // Pull the strongest scored name from this turn's insight events.
    const signal = (message.activity || []).filter((a) => a.kind === 'signals').pop();

    const submit = async (sym, dir, score) => {
        setState('saving');
        try {
            await api.post('/ledger/theses', {
                ticker: sym,
                direction: dir,
                rationale: (message.content || '').slice(0, 8000),
                agent_id: 'copilot',
                composite_score: Number.isFinite(score) ? score : undefined,
            });
            setState('done');
            toast.success(`Logged ${dir} ${sym} to the Conviction Ledger`);
        } catch (err) {
            setState('idle');
            toast.error(err?.response?.data?.detail || 'Could not log the thesis.');
        }
    };

    if (state === 'done') {
        return (
            <div className="mt-2 inline-flex items-center gap-1.5 font-mono text-[11px] text-primary">
                <CheckCircle2 className="h-3 w-3" /> In the ledger — grading nightly vs SPY
            </div>
        );
    }
    if (state === 'form') {
        return (
            <div className="mt-2 flex items-center gap-1.5">
                <input
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value.toUpperCase())}
                    placeholder="TICKER"
                    maxLength={10}
                    className="w-20 rounded border border-border bg-card px-2 py-1 font-mono text-[11px] focus:border-primary/60 focus:outline-none"
                />
                <select
                    value={direction}
                    onChange={(e) => setDirection(e.target.value)}
                    className="rounded border border-border bg-card px-1.5 py-1 font-mono text-[11px]"
                >
                    <option value="long">long</option>
                    <option value="short">short</option>
                </select>
                <button
                    onClick={() => ticker && submit(ticker, direction)}
                    disabled={!ticker}
                    className="rounded border border-primary/40 bg-primary/10 px-2 py-1 font-mono text-[11px] text-primary hover:bg-primary/20 disabled:opacity-40"
                >
                    Log
                </button>
                <button onClick={() => setState('idle')}
                    className="px-1 font-mono text-[11px] text-muted-foreground hover:text-foreground">
                    ×
                </button>
            </div>
        );
    }
    return (
        <button
            onClick={() => {
                if (signal?.symbol) {
                    const score = Number(signal.composite_score);
                    submit(signal.symbol, score < 0 ? 'short' : 'long', score);
                } else {
                    setState('form');
                }
            }}
            disabled={state === 'saving'}
            className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1 font-mono text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary disabled:opacity-40"
            data-testid="log-thesis-btn"
        >
            {state === 'saving' ? <Loader2 className="h-3 w-3 animate-spin" /> : <BookMarked className="h-3 w-3" />}
            {signal?.symbol ? `Log ${signal.symbol} as thesis` : 'Log as thesis'}
        </button>
    );
}

// --- intelligence "insight" renderers --------------------------------------
const scoreColor = (s) =>
    Number(s) >= 25 ? 'text-emerald-500' : Number(s) <= -25 ? 'text-red-500' : 'text-amber-500';

function ScoreMeter({ score }) {
    const v = Number(score) || 0;
    const pct = Math.max(0, Math.min(100, (v + 100) / 2));
    const col = v >= 25 ? 'bg-emerald-500' : v <= -25 ? 'bg-red-500' : 'bg-amber-500';
    return (
        <div className="relative h-1.5 w-full rounded-full bg-muted">
            <span className="absolute left-1/2 top-1/2 h-2.5 w-px -translate-y-1/2 bg-foreground/30" />
            <span className={`absolute top-0 h-1.5 w-2 rounded-full ${col}`} style={{ left: `calc(${pct}% - 4px)` }} />
        </div>
    );
}

function StatTile({ label, value, tone }) {
    return (
        <div className="rounded-lg border border-border bg-muted/40 px-2.5 py-1.5">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
            <div className={`font-mono text-sm font-semibold ${tone || 'text-foreground'}`}>{value}</div>
        </div>
    );
}

function ComplianceCard({ item }) {
    const d = item.decision;
    const tone = d === 'BLOCK'
        ? { c: 'text-red-500 border-red-500/40 bg-red-500/[0.06]', Icon: ShieldX, label: 'Blocked' }
        : d === 'WARN'
            ? { c: 'text-amber-500 border-amber-500/40 bg-amber-500/[0.06]', Icon: ShieldAlert, label: 'Cleared with notes' }
            : { c: 'text-emerald-500 border-emerald-500/40 bg-emerald-500/[0.06]', Icon: ShieldCheck, label: 'Passed' };
    const Icon = tone.Icon;
    return (
        <div className={`rounded-xl border px-3.5 py-2.5 text-xs animate-in fade-in zoom-in-95 duration-300 ${tone.c}`}>
            <div className="flex items-center gap-2 font-semibold">
                <Icon className="h-4 w-4 flex-shrink-0" />
                <span className="text-[11px] uppercase tracking-wider">Pre-trade compliance — {tone.label}</span>
                {item.symbol && (
                    <span className="ml-auto font-mono opacity-80">
                        {(item.side || '').toUpperCase()} {item.qty} {item.symbol}
                    </span>
                )}
            </div>
            {item.summary && <div className="mt-1.5 leading-relaxed text-foreground/80">{item.summary}</div>}
            {Array.isArray(item.checks) && item.checks.length > 0 && (
                <div className="mt-2 space-y-1">
                    {item.checks.map((c, i) => (
                        <div key={i} className="flex items-start gap-1.5 font-mono text-[11px]">
                            <span className={c.status === 'block' ? 'text-red-500' : c.status === 'warn' ? 'text-amber-500' : 'text-emerald-500/80'}>
                                {c.status === 'block' ? '✕' : c.status === 'warn' ? '!' : '✓'}
                            </span>
                            <span className="text-muted-foreground">{c.rule}:</span>
                            <span className="text-foreground/70">{c.detail}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function SignalsInsight({ item }) {
    const s = Number(item.composite_score);
    return (
        <>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-foreground">
                    <Gauge className="h-4 w-4 text-primary" /> {item.symbol} quant score
                </div>
                <span className={`font-mono text-sm font-bold ${scoreColor(s)}`}>{s} · {item.signal_label}</span>
            </div>
            <div className="mt-2"><ScoreMeter score={s} /></div>
            {item.category_scores && (
                <div className="mt-2.5 grid grid-cols-5 gap-1.5">
                    {Object.entries(item.category_scores).map(([k, v]) => (
                        <div key={k} className="text-center">
                            <div className={`font-mono text-xs font-semibold ${scoreColor(Number(v))}`}>{Math.round(Number(v))}</div>
                            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">{k.slice(0, 4)}</div>
                        </div>
                    ))}
                </div>
            )}
        </>
    );
}

function ScanInsight({ item }) {
    const ranked = item.ranked || [];
    return (
        <>
            <div className="mb-2 flex items-center gap-2 font-semibold text-foreground">
                <BarChart3 className="h-4 w-4 text-primary" /> Ranked by quant conviction
            </div>
            <div className="space-y-1">
                {ranked.map((r, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                        <span className="w-4 text-muted-foreground">{i + 1}</span>
                        <span className="w-14 font-mono font-semibold text-foreground">{r.symbol}</span>
                        <div className="flex-1"><ScoreMeter score={Number(r.composite_score)} /></div>
                        <span className={`w-10 text-right font-mono ${scoreColor(Number(r.composite_score))}`}>
                            {Math.round(Number(r.composite_score))}
                        </span>
                    </div>
                ))}
            </div>
        </>
    );
}

function PortfolioRiskInsight({ item }) {
    const worst = (item.stress_tests || []).reduce(
        (a, b) => (a && a.portfolio_pct_change <= b.portfolio_pct_change ? a : b), null);
    return (
        <>
            <div className="mb-2 flex items-center gap-2 font-semibold text-foreground">
                <Shield className="h-4 w-4 text-primary" /> Portfolio risk X-ray
            </div>
            <div className="grid grid-cols-3 gap-1.5">
                <StatTile label="Beta" value={item.portfolio_beta ?? '—'} />
                <StatTile label="95% VaR" value={item.var_95 != null ? `${item.var_95}%` : '—'} tone="text-amber-500" />
                <StatTile label="Max DD" value={item.max_drawdown != null ? `${item.max_drawdown}%` : '—'} tone="text-red-500" />
            </div>
            {worst && (
                <div className="mt-2 text-[11px] text-muted-foreground">
                    Worst stress — <span className="font-mono text-red-500">{worst.scenario} {worst.portfolio_pct_change}%</span>
                </div>
            )}
            {item.concentration_warning && (
                <div className="mt-1 text-[11px] text-muted-foreground">{item.concentration_warning}</div>
            )}
        </>
    );
}

function StockRiskInsight({ item }) {
    const s = item.sizing_recommendation || {};
    return (
        <>
            <div className="mb-2 flex items-center gap-2 font-semibold text-foreground">
                <Crosshair className="h-4 w-4 text-primary" /> {item.ticker} risk profile
            </div>
            <div className="grid grid-cols-3 gap-1.5">
                <StatTile label="Beta" value={item.beta ?? '—'} />
                <StatTile label="Volatility" value={item.annualised_volatility_pct != null ? `${item.annualised_volatility_pct}%` : '—'} />
                <StatTile label="95% VaR" value={item.var_95_daily_pct != null ? `${item.var_95_daily_pct}%` : '—'} tone="text-amber-500" />
            </div>
            {s.label && (
                <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
                    <span className="rounded-full px-2 py-0.5 font-mono uppercase tracking-wide"
                        style={{ color: s.color, background: `${s.color}1a` }}>{s.label}</span>
                    <span className="text-muted-foreground">
                        suggest <span className="font-mono text-foreground">{s.suggested_position_pct}%</span> ·
                        max <span className="font-mono text-foreground">{s.max_position_pct}%</span> ·
                        stop <span className="font-mono text-foreground">{s.stop_loss_pct}%</span>
                    </span>
                </div>
            )}
        </>
    );
}

function BacktestInsight({ item }) {
    const m = item.metrics || {};
    const ret = Number(m.total_return_pct);
    return (
        <>
            <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-foreground">
                    <FlaskConical className="h-4 w-4 text-primary" /> Backtest — {item.strategy_name}
                </div>
                {item.period && (
                    <span className="font-mono text-[10px] text-muted-foreground">{item.period.start} → {item.period.end}</span>
                )}
            </div>
            <div className="grid grid-cols-3 gap-1.5">
                <StatTile label="Return" value={`${m.total_return_pct}%`} tone={ret >= 0 ? 'text-emerald-500' : 'text-red-500'} />
                <StatTile label="Sharpe" value={m.sharpe} />
                <StatTile label="Max DD" value={`${m.max_drawdown_pct}%`} tone="text-red-500" />
                <StatTile label="CAGR" value={`${m.cagr_pct}%`} />
                <StatTile label="Win rate" value={`${m.win_rate_pct}%`} />
                <StatTile label="Trades" value={m.num_trades} />
            </div>
        </>
    );
}

function ResearchInsight({ item }) {
    const specialists = item.specialists || [];
    return (
        <>
            <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-foreground">
                    <Users className="h-4 w-4 text-primary" /> Research team — {item.symbol}
                </div>
                {item.signal_label && (
                    <span className={`font-mono text-sm font-bold ${scoreColor(item.signal_score)}`}>
                        {item.signal_label} · {item.signal_score}
                    </span>
                )}
            </div>
            <div className="flex flex-wrap gap-1.5">
                {specialists.map((s) => (
                    <span key={s} className="rounded-full border border-border bg-muted/50 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                        {s}
                    </span>
                ))}
            </div>
            <div className="mt-2 text-[11px] text-muted-foreground">
                {specialists.length} specialists synthesized → full memo below.
            </div>
        </>
    );
}

const GRADE_TONE = {
    A: 'text-emerald-500 border-emerald-500/40 bg-emerald-500/10',
    B: 'text-emerald-500 border-emerald-500/30 bg-emerald-500/[0.07]',
    C: 'text-amber-500 border-amber-500/40 bg-amber-500/10',
    D: 'text-orange-500 border-orange-500/40 bg-orange-500/10',
    F: 'text-red-500 border-red-500/40 bg-red-500/10',
};

function ReviewInsight({ item }) {
    const stats = item.stats || {};
    const lessons = item.lessons || [];
    const gradeKey = (item.grade || '').toString().charAt(0).toUpperCase();
    const gradeTone = GRADE_TONE[gradeKey] || 'text-muted-foreground border-border';
    return (
        <>
            <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-foreground">
                    <GraduationCap className="h-4 w-4 text-primary" /> Self-review &amp; learning
                </div>
                {item.grade && (
                    <span className={`flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wide ${gradeTone}`}>
                        <Award className="h-3 w-3" /> {item.grade}
                    </span>
                )}
            </div>
            {item.assessment && <div className="leading-relaxed text-foreground/80">{item.assessment}</div>}
            <div className="mt-2 grid grid-cols-3 gap-1.5">
                <StatTile label="Period" value={stats.period_return_pct != null ? `${stats.period_return_pct}%` : '—'}
                    tone={Number(stats.period_return_pct) >= 0 ? 'text-emerald-500' : 'text-red-500'} />
                <StatTile label="Positions" value={stats.open_positions ?? '—'} />
                <StatTile label="Reviewed" value={stats.decisions_reviewed ?? '—'} />
            </div>
            {lessons.length > 0 && (
                <div className="mt-2.5">
                    <div className="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-primary">
                        <Brain className="h-3 w-3" /> {item.lessons_learned_count > 0
                            ? `Committed ${item.lessons_learned_count} lesson(s) to memory`
                            : 'Lessons'}
                    </div>
                    <ul className="space-y-1">
                        {lessons.map((l, i) => (
                            <li key={i} className="flex items-start gap-1.5 text-[11px] text-foreground/75">
                                <span className="mt-1 h-1 w-1 flex-shrink-0 rounded-full bg-primary/70" />
                                {l}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </>
    );
}

const REGIME_TONE = {
    'risk-on': 'text-emerald-500', constructive: 'text-emerald-500', neutral: 'text-amber-500',
    cautious: 'text-orange-500', 'risk-off': 'text-red-500',
};

function RegimeInsight({ item }) {
    const tone = REGIME_TONE[item.risk_state] || 'text-foreground';
    return (
        <>
            <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-foreground">
                    <Compass className="h-4 w-4 text-primary" /> Market regime
                </div>
                <span className={`font-mono text-sm font-bold ${tone}`}>{item.regime_label}</span>
            </div>
            <div className="grid grid-cols-3 gap-1.5">
                <StatTile label="VIX" value={item.vix != null ? `${item.vix} · ${item.vix_band}` : '—'} />
                <StatTile label="SPY trend" value={item.spy_trend || '—'}
                    tone={item.spy_trend === 'uptrend' ? 'text-emerald-500' : item.spy_trend === 'downtrend' ? 'text-red-500' : undefined} />
                <StatTile label="Breadth" value={item.breadth_pct != null ? `${item.breadth_pct}%` : '—'} />
            </div>
            <div className="mt-2 flex items-center gap-2 text-[11px]">
                <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 font-mono text-primary">
                    Exposure {item.suggested_gross_exposure}
                </span>
                <span className="text-muted-foreground">{item.playbook}</span>
            </div>
        </>
    );
}

function SimulationInsight({ item }) {
    const before = item.before || {}, after = item.after || {};
    const d = item.compliance_decision;
    const decTone = d === 'BLOCK' ? 'text-red-500 border-red-500/40 bg-red-500/10'
        : d === 'WARN' ? 'text-amber-500 border-amber-500/40 bg-amber-500/10'
            : 'text-emerald-500 border-emerald-500/40 bg-emerald-500/10';
    return (
        <>
            <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-foreground">
                    <Calculator className="h-4 w-4 text-primary" /> What-if: {(item.side || '').toUpperCase()} {item.qty} {item.symbol}
                </div>
                {d && <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${decTone}`}>{d}</span>}
            </div>
            <div className="grid grid-cols-2 gap-2">
                {[['Before', before], ['After', after]].map(([label, s]) => (
                    <div key={label} className="rounded-lg border border-border bg-muted/40 px-2.5 py-2">
                        <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
                        <div className="flex justify-between font-mono text-xs"><span className="text-muted-foreground">Weight</span><span className="font-semibold text-foreground">{s.weight_pct}%</span></div>
                        <div className="flex justify-between font-mono text-xs"><span className="text-muted-foreground">Cash</span><span className="text-foreground">${Math.round(s.cash || 0).toLocaleString()}</span></div>
                        <div className="flex justify-between font-mono text-xs"><span className="text-muted-foreground">Buying pwr</span><span className="text-foreground">${Math.round(s.buying_power || 0).toLocaleString()}</span></div>
                    </div>
                ))}
            </div>
            {item.largest_position_after && (
                <div className="mt-2 text-[11px] text-muted-foreground">
                    Largest position after — <span className="font-mono text-foreground">{item.largest_position_after.symbol} {item.largest_position_after.weight_pct}%</span>
                </div>
            )}
        </>
    );
}

const VERDICT_TONE = {
    Bullish: 'text-emerald-500 border-emerald-500/40 bg-emerald-500/10',
    Bearish: 'text-red-500 border-red-500/40 bg-red-500/10',
    Neutral: 'text-amber-500 border-amber-500/40 bg-amber-500/10',
};

function DebateInsight({ item }) {
    const vTone = VERDICT_TONE[item.verdict] || 'text-muted-foreground border-border';
    return (
        <>
            <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-foreground">
                    <Swords className="h-4 w-4 text-primary" /> Bull vs Bear — {item.symbol}
                </div>
                {item.verdict && (
                    <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide ${vTone}`}>
                        {item.verdict}{item.conviction ? ` · ${item.conviction}` : ''}
                    </span>
                )}
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/[0.05] p-2.5">
                    <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-500">
                        <TrendingUp className="h-3 w-3" /> Bull case
                    </div>
                    <p className="text-[11px] leading-relaxed text-foreground/80">{item.bull_case || '—'}</p>
                </div>
                <div className="rounded-lg border border-red-500/30 bg-red-500/[0.05] p-2.5">
                    <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-red-500">
                        <TrendingDown className="h-3 w-3" /> Bear case
                    </div>
                    <p className="text-[11px] leading-relaxed text-foreground/80">{item.bear_case || '—'}</p>
                </div>
            </div>
            {(item.summary || item.recommended_action) && (
                <div className="mt-2 rounded-lg border border-border bg-muted/40 p-2.5">
                    {item.recommended_action && (
                        <div className="text-[11px] text-foreground/90"><span className="font-semibold text-foreground">Action:</span> {item.recommended_action}</div>
                    )}
                    {item.summary && <div className="mt-1 text-[11px] text-muted-foreground">{item.summary}</div>}
                    {item.key_swing_factor && <div className="mt-1 text-[11px] text-muted-foreground"><span className="text-foreground/70">Swing factor:</span> {item.key_swing_factor}</div>}
                </div>
            )}
        </>
    );
}

function EarningsInsight({ item }) {
    const days = item.days_until_earnings;
    const near = typeof days === 'number' && days >= 0 && days <= 7;
    const sp = item.surprise_probability || {};
    const bs = item.beat_statistics || {};
    return (
        <>
            <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-foreground">
                    <CalendarClock className="h-4 w-4 text-primary" /> Earnings catalyst — {item.symbol}
                </div>
                {item.next_earnings_date && (
                    <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${near ? 'text-amber-500 border-amber-500/40 bg-amber-500/10' : 'text-muted-foreground border-border'}`}>
                        {item.next_earnings_date}{typeof days === 'number' ? ` · ${days}d` : ''}
                    </span>
                )}
            </div>
            <div className="grid grid-cols-2 gap-1.5">
                <StatTile label="Beat rate" value={bs.beat_rate != null ? `${bs.beat_rate}%` : (bs.beats != null ? `${bs.beats}/${bs.total ?? '?'}` : '—')} />
                <StatTile label="Surprise lean" value={sp.direction || sp.label || sp.probability != null ? (sp.direction || sp.label || `${sp.probability}%`) : '—'} />
            </div>
            {near && (
                <div className="mt-2 text-[11px] text-amber-500">⚠ Earnings within a week — consider waiting or sizing smaller.</div>
            )}
        </>
    );
}

function InsightCard({ item }) {
    let body = null;
    if (item.kind === 'signals') body = <SignalsInsight item={item} />;
    else if (item.kind === 'scan') body = <ScanInsight item={item} />;
    else if (item.kind === 'portfolio_risk') body = <PortfolioRiskInsight item={item} />;
    else if (item.kind === 'stock_risk') body = <StockRiskInsight item={item} />;
    else if (item.kind === 'backtest') body = <BacktestInsight item={item} />;
    else if (item.kind === 'research') body = <ResearchInsight item={item} />;
    else if (item.kind === 'review') body = <ReviewInsight item={item} />;
    else if (item.kind === 'regime') body = <RegimeInsight item={item} />;
    else if (item.kind === 'simulation') body = <SimulationInsight item={item} />;
    else if (item.kind === 'debate') body = <DebateInsight item={item} />;
    else if (item.kind === 'earnings') body = <EarningsInsight item={item} />;
    else return null;
    return (
        <div className="rounded-xl border border-border bg-card px-3.5 py-3 text-xs shadow-sm animate-in fade-in zoom-in-95 duration-300">
            {body}
        </div>
    );
}

function ActivityTimeline({ items, onTradeAction }) {
    if (!items?.length) return null;
    return (
        <div className="relative mb-3 space-y-2 pl-4">
            <span className="absolute bottom-1 left-0 top-1 w-px bg-gradient-to-b from-primary/40 via-primary/15 to-transparent" />
            {items.map((it, i) => {
                if (it.kind === 'thinking') return <ThinkingRow key={i} text={it.message} />;
                if (it.kind === 'tool') return <ToolPill key={i} item={it} />;
                if (it.kind === 'compliance') return <ComplianceCard key={i} item={it} />;
                if (it.kind === 'insight') return <InsightCard key={i} item={it} />;
                if (it.kind === 'trade') return <TradeCard key={i} t={it} onAction={onTradeAction} />;
                return null;
            })}
        </div>
    );
}

function AgentAvatar({ size = 'sm' }) {
    const dim = size === 'lg' ? 'h-14 w-14' : 'h-8 w-8';
    const icon = size === 'lg' ? 'h-7 w-7' : 'h-4 w-4';
    return (
        <div className={`relative flex ${dim} flex-shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/25 to-primary/5 ring-1 ring-primary/30 shadow-[0_0_24px_-6px_hsl(var(--primary)/0.55)]`}>
            <Plane className={`${icon} text-primary`} />
        </div>
    );
}

// Reusable centered composer — used both on the landing screen and docked below.
function Composer({ input, setInput, onSend, onStop, loading, autoFocus, placeholder, onCommand }) {
    const taRef = useRef(null);
    const firstToken = input.split(/\s/)[0].toLowerCase();
    const showSlash = input.startsWith('/') && !input.includes(' ');
    const matches = showSlash ? SLASH.filter((s) => s.cmd.startsWith(firstToken)) : [];

    const pick = (s) => {
        if (s.prompt) { setInput(''); onCommand?.(s.prompt); }
        else { setInput(s.stub); setTimeout(() => taRef.current?.focus(), 0); }
    };

    return (
        <div className="relative rounded-2xl border border-border bg-card shadow-lg shadow-black/5 transition-all focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/15">
            {matches.length > 0 && (
                <div className="absolute bottom-full left-0 right-0 mb-2 max-h-72 overflow-y-auto rounded-xl border border-border bg-popover shadow-xl animate-in fade-in slide-in-from-bottom-1 duration-150">
                    <div className="sticky top-0 flex items-center gap-1.5 border-b border-border bg-popover px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                        <Slash className="h-3 w-3" /> Commands
                    </div>
                    {matches.map((s) => {
                        const Icon = s.icon;
                        return (
                            <button key={s.cmd} type="button" onClick={() => pick(s)}
                                className="flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors hover:bg-muted">
                                <Icon className="h-3.5 w-3.5 flex-shrink-0 text-primary" />
                                <span className="font-mono text-xs font-semibold text-foreground">{s.cmd}</span>
                                <span className="truncate text-[11px] text-muted-foreground">{s.desc}</span>
                            </button>
                        );
                    })}
                </div>
            )}
            <textarea
                ref={taRef}
                value={input}
                autoFocus={autoFocus}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        if (matches.length > 0) { e.preventDefault(); pick(matches[0]); return; }
                        e.preventDefault(); onSend();
                    }
                }}
                rows={1}
                placeholder={placeholder || 'Describe a trade idea, ask a question, or type / for commands…'}
                className="max-h-40 w-full resize-none bg-transparent px-4 pt-3.5 pb-1.5 text-sm text-foreground outline-none placeholder:text-muted-foreground/70"
            />
            <div className="flex items-center justify-between px-3 pb-2.5">
                <span className="font-mono text-[10px] text-muted-foreground/70">
                    <kbd className="rounded bg-muted px-1">/</kbd> commands · <kbd className="rounded bg-muted px-1">⏎</kbd> send
                </span>
                {loading ? (
                    <Button onClick={onStop} size="sm" variant="outline" className="h-8 gap-1.5 rounded-xl">
                        <Square className="h-3 w-3 fill-current" /> Stop
                    </Button>
                ) : (
                    <Button onClick={onSend} size="sm" disabled={!input.trim()} className="h-8 gap-1.5 rounded-xl shadow-lg shadow-primary/20">
                        <Send className="h-3.5 w-3.5" /> Send
                    </Button>
                )}
            </div>
        </div>
    );
}

export default function CopilotAgent() {
    const { session } = useAuth();
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [memorySignal, setMemorySignal] = useState(0);
    const [showMemory, setShowMemory] = useState(false);
    const [models, setModels] = useState([]);
    const [model, setModel] = useState(() => localStorage.getItem('copilot_model') || 'gemini-2.5-flash');
    const [confirm, setConfirm] = useState(() => localStorage.getItem('copilot_confirm') !== 'false');
    const [mode, setMode] = useState(() => localStorage.getItem('copilot_mode') === 'research' ? 'research' : 'trade');
    const sessionId = useRef(`copilot_${Date.now()}`);
    const scrollRef = useRef(null);
    const abortRef = useRef(null);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }, [messages]);

    useEffect(() => {
        api.get('/copilot/models').then(({ data }) => {
            const items = data?.items || [];
            setModels(items);
            setModel((cur) => (items.some((m) => m.key === cur) ? cur : (data?.default || 'gemini-2.5-flash')));
        }).catch(() => { /* keep default */ });
    }, []);

    const onModelChange = useCallback((key) => {
        setModel(key);
        localStorage.setItem('copilot_model', key);
    }, []);

    const toggleConfirm = useCallback(() => {
        setConfirm((c) => { localStorage.setItem('copilot_confirm', String(!c)); return !c; });
    const toggleMode = () =>
        setMode((m) => { const n = m === 'trade' ? 'research' : 'trade'; localStorage.setItem('copilot_mode', n); return n; });
    }, []);

    const patchTradeByProposal = useCallback((pid, updates) => {
        setMessages((prev) => prev.map((m) => {
            if (m.role !== 'assistant' || !m.activity) return m;
            return { ...m, activity: m.activity.map((it) =>
                (it.kind === 'trade' && it.proposal_id === pid) ? { ...it, ...updates } : it) };
        }));
    }, []);

    const handleTradeAction = useCallback(async (pid, action) => {
        if (!pid) return;
        patchTradeByProposal(pid, { resolving: action });
        try {
            const { data } = await api.post(`/copilot/trades/${pid}/${action}`);
            if (action === 'approve') {
                const res = data?.item || {};
                if (res.ok) {
                    patchTradeByProposal(pid, { resolved: 'executed', status: res.status || 'accepted', price: res.filled_avg_price, resolving: null });
                    toast.success('Trade approved & sent', { description: 'Paper account' });
                } else {
                    patchTradeByProposal(pid, { resolving: null });
                    toast.error('Execution failed', { description: res.error || 'Broker rejected the order' });
                }
            } else {
                patchTradeByProposal(pid, { resolved: 'rejected', resolving: null });
                toast('Trade rejected');
            }
        } catch (err) {
            patchTradeByProposal(pid, { resolving: null });
            toast.error('Action failed', { description: err?.message });
        }
    }, [patchTradeByProposal]);

    // Pick up a strategy handed off from the Strategy Studio.
    useEffect(() => {
        const handoff = sessionStorage.getItem('copilot_handoff');
        if (handoff) {
            setInput(`Review this strategy from the Strategy Studio and, if it's sound, size and execute the trade on my paper account:\n\n${handoff}`);
            sessionStorage.removeItem('copilot_handoff');
        }
    }, []);

    const patchLastAssistant = useCallback((updater) => {
        setMessages((prev) => {
            const n = [...prev];
            for (let i = n.length - 1; i >= 0; i--) {
                if (n[i].role === 'assistant') { n[i] = updater({ ...n[i] }); break; }
            }
            return n;
        });
    }, []);

    const send = useCallback(async (text) => {
        const msg = (text ?? input).trim();
        if (!msg || loading) return;

        setMessages((prev) => [
            ...prev,
            { id: nextId(), role: 'user', content: msg },
            { id: nextId(), role: 'assistant', content: '', activity: [], streaming: true },
        ]);
        setInput('');
        setLoading(true);

        const controller = new AbortController();
        abortRef.current = controller;

        try {
            const authHeaders = session?.access_token
                ? { 'Content-Type': 'application/json', 'Authorization': `Bearer ${session.access_token}` }
                : { 'Content-Type': 'application/json' };
            const res = await fetch(`${API_BASE}/api/copilot/chat/stream`, {
                method: 'POST',
                headers: authHeaders,
                credentials: 'include',
                body: JSON.stringify({ message: msg, session_id: sessionId.current, model, confirm, mode }),
                signal: controller.signal,
            });
            if (!res.ok || !res.body) throw new Error(`Request failed (${res.status})`);

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let lastEventId = null;

            const handle = (event) => {
                if (event.type === 'thinking') {
                    patchLastAssistant((m) => ({ ...m, activity: [...m.activity, { kind: 'thinking', message: event.message }] }));
                } else if (event.type === 'tool_call') {
                    patchLastAssistant((m) => ({
                        ...m,
                        activity: [...m.activity, {
                            kind: 'tool', name: event.name, label: event.label,
                            is_trade: event.is_trade, args: event.args, status: null,
                            startedAt: Date.now(),
                        }],
                    }));
                } else if (event.type === 'tool_result') {
                    patchLastAssistant((m) => {
                        const act = [...m.activity];
                        for (let i = act.length - 1; i >= 0; i--) {
                            if (act[i].kind === 'tool' && act[i].name === event.name && act[i].status == null) {
                                const elapsed = act[i].startedAt ? Math.max(1, Math.round((Date.now() - act[i].startedAt) / 1000)) : null;
                                act[i] = { ...act[i], status: 'done', ok: event.ok, summary: event.summary, elapsed };
                                break;
                            }
                        }
                        return { ...m, activity: act };
                    });
                } else if (event.type === 'trade') {
                    patchLastAssistant((m) => ({ ...m, activity: [...m.activity, { kind: 'trade', ...event }] }));
                    if (event.pending) {
                        const what = event.action === 'cancel_all' ? 'Cancel all orders'
                            : event.action === 'close' ? `Close ${event.symbol}`
                                : `${event.side === 'buy' ? 'Buy' : 'Sell'} ${event.qty} ${event.symbol}`;
                        toast('Trade staged — approve below', { description: what });
                    } else {
                        const verb = event.action === 'cancel_all' ? 'Cancelled all orders'
                            : event.action === 'close' ? `Closed ${event.symbol}`
                                : `${event.side === 'buy' ? 'Bought' : 'Sold'} ${event.qty} ${event.symbol}`;
                        toast.success(verb, { description: `Status: ${event.status || 'submitted'} · paper account` });
                    }
                } else if (event.type === 'compliance') {
                    patchLastAssistant((m) => ({ ...m, activity: [...m.activity, { kind: 'compliance', ...event }] }));
                    if (event.decision === 'BLOCK') {
                        toast.error('Order blocked by compliance', { description: event.summary });
                    }
                } else if (event.type === 'insight') {
                    patchLastAssistant((m) => ({ ...m, activity: [...m.activity, { kind: 'insight', ...event }] }));
                } else if (event.type === 'token') {
                    patchLastAssistant((m) => ({ ...m, content: m.content + (event.content || '') }));
                } else if (event.type === 'done') {
                    patchLastAssistant((m) => ({ ...m, streaming: false }));
                    setMemorySignal((s) => s + 1);
                    if (event.error) toast.error('Copilot error', { description: event.error });
                }
            };

            for (;;) {
                const { value, done } = await reader.read();
                buffer += value ? decoder.decode(value, { stream: !done }) : '';
                const lines = buffer.split('\n');
                buffer = done ? '' : lines.pop() || '';
                for (const line of lines) {
                    const t = line.trim();
                    if (t.startsWith('id: ')) { lastEventId = t.slice(4); continue; }
                    if (!t.startsWith('data: ')) continue;
                    try { handle(JSON.parse(t.slice(6))); } catch { /* skip malformed */ }
                }
                if (done) break;
            }
            void lastEventId;
        } catch (err) {
            if (err.name !== 'AbortError') {
                const errMsg = err.message || 'The copilot could not respond.';
                patchLastAssistant((m) => ({
                    ...m,
                    streaming: false,
                    content: m.content
                        ? `${m.content}\n\n⚠ *Connection lost — response may be incomplete. ${errMsg}*`
                        : `⚠ ${errMsg}`,
                    streamError: errMsg,
                    retryMessage: msg,
                }));
                toast.error('Copilot request failed', { description: errMsg });
            }
        } finally {
            setLoading(false);
            abortRef.current = null;
        }
    }, [input, loading, model, confirm, mode, patchLastAssistant, session?.access_token]);

    const stop = () => { abortRef.current?.abort(); abortRef.current = null; setLoading(false); patchLastAssistant((m) => ({ ...m, streaming: false })); };

    const empty = messages.length === 0;

    // --- shared control cluster (confirm / model / memory) ------------------
    const Controls = (
        <div className="flex items-center gap-2">
            <button
                onClick={toggleMode}
                title={mode === 'research'
                    ? 'Research-only: trading tools are disabled this session — the agent analyzes and recommends, nothing executes.'
                    : 'Trade mode: the agent can stage/execute paper trades (subject to the confirm toggle).'}
                className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
                    mode === 'research' ? 'border-sky-400/40 bg-sky-400/10 text-sky-400'
                        : 'border-border bg-card text-muted-foreground hover:text-foreground'
                }`}
                data-testid="copilot-mode-toggle"
            >
                {mode === 'research' ? <Brain className="h-3.5 w-3.5" /> : <Crosshair className="h-3.5 w-3.5" />}
                {mode === 'research' ? 'Research-only' : 'Trade mode'}
            </button>
            <button
                onClick={toggleConfirm}
                title={confirm ? 'Confirm before trade: every trade is staged for your one-click approval before it hits the broker.' : 'Execute automatically: the agent places paper trades without asking.'}
                className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
                    confirm ? 'border-primary/30 bg-primary/10 text-primary'
                        : 'border-amber-500/40 bg-amber-500/10 text-amber-500'
                }`}
            >
                {confirm ? <ShieldCheck className="h-3.5 w-3.5" /> : <Zap className="h-3.5 w-3.5" />}
                {confirm ? 'Confirm trades' : 'Auto-execute'}
            </button>
            <div className="flex items-center gap-1.5 rounded-full border border-border bg-card py-1 pl-2.5 pr-1.5" title="Model">
                <Cpu className="h-3.5 w-3.5 text-primary" />
                <select
                    value={model}
                    onChange={(e) => onModelChange(e.target.value)}
                    className="max-w-[150px] cursor-pointer bg-transparent pr-1 font-mono text-[11px] text-foreground outline-none"
                >
                    {models.length === 0 && <option value={model}>{model}</option>}
                    {models.map((m) => (
                        <option key={m.key} value={m.key} className="bg-popover text-popover-foreground">
                            {m.label}{m.experimental ? ' · beta' : ''}
                        </option>
                    ))}
                </select>
            </div>
            <button
                onClick={() => setShowMemory((v) => !v)}
                title="What the copilot remembers about you"
                className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
                    showMemory ? 'border-primary/30 bg-primary/10 text-primary' : 'border-border bg-card text-muted-foreground hover:text-foreground'
                }`}
            >
                <History className="h-3.5 w-3.5" /> Memory
            </button>
        </div>
    );

    return (
        <div className="mx-auto flex min-h-[calc(100vh-180px)] w-full max-w-3xl flex-col">
            {/* Slim, unobtrusive control row */}
            <div className="flex items-center justify-between gap-3 pb-3">
                <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
                    <span className="relative flex h-1.5 w-1.5">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/70" />
                        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
                    </span>
                    Copilot · Autonomous · Paper
                </div>
                {Controls}
            </div>

            {showMemory && (
                <div className="mb-3 rounded-2xl border border-border bg-card p-4 shadow-sm animate-in fade-in slide-in-from-top-1 duration-200">
                    <CopilotMemory refreshSignal={memorySignal} />
                </div>
            )}

            {empty ? (
                /* ---------------- Landing ---------------- */
                <div className="flex flex-1 flex-col items-center justify-center px-2 py-8 text-center">
                    <AgentAvatar size="lg" />
                    <h1 className="mt-5 text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
                        Describe a trade idea, ask a question, get help
                    </h1>
                    <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
                        I research the market, score conviction, size to risk, backtest the idea, clear
                        compliance, and execute paper trades — showing every step I take.
                    </p>

                    <div className="mt-6 w-full max-w-2xl">
                        <Composer input={input} setInput={setInput} onSend={() => send()} onStop={stop} loading={loading} onCommand={send} autoFocus />
                        <div className={`mx-auto mt-2 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] ${
                            confirm ? 'border-primary/25 bg-primary/[0.06] text-primary' : 'border-amber-500/35 bg-amber-500/[0.06] text-amber-500'
                        }`}>
                            {confirm ? <ShieldCheck className="h-3 w-3" /> : <Zap className="h-3 w-3" />}
                            {confirm ? 'Confirm-before-trade is on — nothing executes without your approval.'
                                : 'Auto-execute is on — paper trades place without asking.'}
                        </div>
                    </div>

                    <div className="mt-7 grid w-full max-w-3xl gap-3 sm:grid-cols-3">
                        {HERO_CARDS.map(({ icon: Icon, title, sub, prompt }) => (
                            <button key={title} onClick={() => send(prompt)}
                                className="group flex flex-col items-start rounded-2xl border border-border bg-card p-4 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md">
                                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20 transition-colors group-hover:bg-primary/20">
                                    <Icon className="h-5 w-5" />
                                </span>
                                <span className="mt-3 text-sm font-semibold text-foreground">{title}</span>
                                <span className="mt-1 text-xs leading-snug text-muted-foreground">{sub}</span>
                            </button>
                        ))}
                    </div>

                    <div className="mt-4 flex flex-wrap justify-center gap-1.5">
                        {SUGGESTIONS.map((text) => (
                            <button key={text} onClick={() => send(text)}
                                className="rounded-full border border-border bg-card px-3 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground">
                                {text}
                            </button>
                        ))}
                    </div>
                </div>
            ) : (
                /* ---------------- Conversation ---------------- */
                <>
                    <div ref={scrollRef} className="flex-1 space-y-6 overflow-y-auto px-1 py-2 scroll-smooth">
                        {messages.map((m) => (
                            m.role === 'user' ? (
                                <div key={m.id} className="flex justify-end animate-in fade-in slide-in-from-right-2 duration-300">
                                    <div className="max-w-[85%] rounded-2xl rounded-br-md border border-border bg-muted px-4 py-2.5 text-sm text-foreground">
                                        {m.content}
                                    </div>
                                </div>
                            ) : (
                                <div key={m.id} className="flex gap-3 animate-in fade-in slide-in-from-bottom-1 duration-300">
                                    <AgentAvatar />
                                    <div className="min-w-0 flex-1 pt-0.5">
                                        <ActivityTimeline items={m.activity} onTradeAction={handleTradeAction} />
                                        {m.content ? (
                                            <>
                                                <RichMarkdown>{m.content}</RichMarkdown>
                                                {!m.streaming && <LogThesisButton message={m} />}
                                            </>
                                        ) : m.streaming && !m.activity?.length ? (
                                            <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                                                <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" /> thinking…
                                            </div>
                                        ) : null}
                                        {m.streamError && m.retryMessage && (
                                            <button
                                                onClick={() => send(m.retryMessage)}
                                                disabled={loading}
                                                className="mt-2 flex items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/[0.07] px-3 py-1.5 font-mono text-xs text-amber-500 transition-colors hover:border-amber-500/50 hover:bg-amber-500/[0.12] disabled:opacity-40"
                                            >
                                                <Loader2 className="h-3 w-3" /> Retry last message
                                            </button>
                                        )}
                                    </div>
                                </div>
                            )
                        ))}
                    </div>

                    {/* Docked floating composer */}
                    <div className="sticky bottom-0 mt-2 bg-gradient-to-t from-background via-background to-transparent pb-1 pt-3">
                        <div className="mb-2 flex flex-wrap gap-1.5">
                            {SUGGESTIONS.slice(0, 3).map((text) => (
                                <button key={text} onClick={() => send(text)} disabled={loading}
                                    className="rounded-full border border-border bg-card px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground disabled:opacity-40">
                                    {text.length > 40 ? text.slice(0, 38) + '…' : text}
                                </button>
                            ))}
                        </div>
                        <Composer input={input} setInput={setInput} onSend={() => send()} onStop={stop} loading={loading} onCommand={send} placeholder="Reply… or / for commands" />
                        <p className="mt-2 text-center text-[11px] text-muted-foreground/70">
                            AI can make mistakes. Paper trading — educational, not investment advice.
                        </p>
                    </div>
                </>
            )}
        </div>
    );
}
