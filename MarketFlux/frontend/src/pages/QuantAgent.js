import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import {
  Activity, AlertTriangle, BrainCircuit, CheckCircle2,
  ChevronRight, Download, Loader2, Play, ShieldAlert,
  Sparkles, BarChart2, List, RefreshCw,
  ArrowRight, FlaskConical
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow
} from '@/components/ui/table';
import { API_BASE } from '@/lib/api';

// ─── helpers ────────────────────────────────────────────────────────────────

function fmt2(v) {
  if (v === null || v === undefined) return '--';
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(v) {
  if (v === null || v === undefined) return '--';
  const n = Number(v);
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

function fmtCurrency(v) {
  if (v === null || v === undefined) return '--';
  return `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

const STRATEGY_LABELS = {
  sma_crossover: 'SMA Crossover',
  rsi_mean_reversion: 'RSI Mean Reversion',
  momentum: 'Momentum',
};

const RISK_PROFILES = ['conservative', 'balanced', 'aggressive'];

const METRIC_COLOR = (v, goodHigh = true) => {
  if (v === null || v === undefined) return 'text-muted-foreground';
  const n = Number(v);
  if (goodHigh) return n >= 0 ? 'text-[#00ff88]' : 'text-[#ff4444]';
  return n <= 0 ? 'text-[#00ff88]' : 'text-[#ff4444]'; // lower is better (drawdown)
};

// ─── sub-components ─────────────────────────────────────────────────────────

function MetricCard({ label, value, sub, colorFn, unit = '' }) {
  const colorClass = colorFn ? colorFn(value) : 'text-foreground';
  return (
    <div className="rounded-[14px] border border-white/8 bg-white/3 p-4 flex flex-col gap-1">
      <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
      <div className={`text-2xl font-semibold font-mono ${colorClass}`}>
        {value !== null && value !== undefined ? `${value}${unit}` : '--'}
      </div>
      {sub && <div className="text-[11px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

function StrategyBadge({ stratId, active }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-mono uppercase tracking-[0.14em] ${
      active
        ? 'bg-primary/20 text-primary border border-primary/30'
        : 'bg-white/5 text-muted-foreground border border-white/10'
    }`}>
      {active && <CheckCircle2 className="w-3 h-3" />}
      {STRATEGY_LABELS[stratId] || stratId}
    </span>
  );
}

function StepIndicator({ steps, currentStep }) {
  return (
    <div className="flex flex-col gap-1.5">
      {steps.map((s, i) => {
        const isDone = i < currentStep;
        const isCurrent = i === currentStep;
        return (
          <div key={i} className={`flex items-start gap-3 text-sm transition-opacity ${
            isDone ? 'opacity-100' : isCurrent ? 'opacity-100' : 'opacity-30'
          }`}>
            <div className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
              isDone ? 'bg-primary/20 text-primary' : isCurrent ? 'bg-amber-500/20 text-amber-400' : 'bg-white/5 text-muted-foreground'
            }`}>
              {isDone ? <CheckCircle2 className="w-3 h-3" /> : isCurrent ? <Loader2 className="w-3 h-3 animate-spin" /> : <ChevronRight className="w-3 h-3" />}
            </div>
            <div>
              <div className={`font-mono text-xs uppercase tracking-wider ${isCurrent ? 'text-amber-400' : isDone ? 'text-primary' : 'text-muted-foreground'}`}>{s.label}</div>
              {isCurrent && s.message && (
                <div className="text-muted-foreground text-[11px] mt-0.5 leading-relaxed">{s.message}</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BacktestChart({ data, title }) {
  if (!data || data.length === 0) return null;
  return (
    <div className="space-y-2">
      <div className="text-xs font-mono uppercase tracking-wider text-muted-foreground">{title}</div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
          <Tooltip
            contentStyle={{ background: '#0d1117', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
            formatter={(v, name) => [`$${Number(v).toLocaleString()}`, name === 'portfolio' ? 'Strategy' : 'Buy & Hold']}
          />
          <Legend wrapperStyle={{ fontSize: 11, paddingTop: 4 }} />
          <Line type="monotone" dataKey="portfolio" stroke="#00ff88" dot={false} strokeWidth={1.5} name="Strategy" />
          <Line type="monotone" dataKey="buy_hold" stroke="#6366f1" dot={false} strokeWidth={1.5} name="Buy & Hold" strokeDasharray="4 2" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function DrawdownChart({ data }) {
  if (!data || data.length === 0) return null;
  return (
    <div className="space-y-2">
      <div className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Drawdown</div>
      <ResponsiveContainer width="100%" height={150}>
        <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} tickFormatter={v => `${v.toFixed(0)}%`} />
          <Tooltip
            contentStyle={{ background: '#0d1117', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
            formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Drawdown']}
          />
          <Area type="monotone" dataKey="drawdown" stroke="#ef4444" fill="#ef444420" strokeWidth={1.5} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function MonthlyReturnBars({ data }) {
  if (!data || data.length === 0) return null;
  return (
    <div className="space-y-2">
      <div className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Monthly Returns</div>
      <ResponsiveContainer width="100%" height={150}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="month" tick={{ fill: '#6b7280', fontSize: 9 }} tickLine={false} />
          <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} tickFormatter={v => `${v.toFixed(0)}%`} />
          <Tooltip
            contentStyle={{ background: '#0d1117', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 11 }}
            formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Return']}
          />
          <Bar dataKey="return_pct" fill="#00ff88" radius={[3, 3, 0, 0]}
               label={false}
               isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Paper trading deploy dialog ─────────────────────────────────────────────

function DeployDialog({ strategy, bestBacktest, capital, ticker, alpacaConnected, onDeploy, onCancel }) {
  const metrics = bestBacktest?.metrics || {};
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-[24px] border border-primary/30 bg-[#0d1117] p-6 space-y-5 shadow-2xl">
        <div className="flex items-center gap-3">
          <div className="rounded-full bg-primary/10 p-2"><ShieldAlert className="w-5 h-5 text-primary" /></div>
          <div>
            <div className="font-semibold text-foreground">Deploy to Paper Trading</div>
            <div className="text-xs text-muted-foreground font-mono mt-0.5">Human approval required before any live trade</div>
          </div>
        </div>

        <div className="rounded-[16px] border border-white/8 bg-white/3 p-4 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Ticker</span>
            <span className="font-mono font-semibold text-foreground">{ticker}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Capital</span>
            <span className="font-mono">{fmtCurrency(capital)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Best Backtest Sharpe</span>
            <span className={`font-mono ${METRIC_COLOR(metrics.sharpe_ratio)}`}>
              {metrics.sharpe_ratio ?? '--'}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Backtest Return</span>
            <span className={`font-mono ${METRIC_COLOR(metrics.total_return_pct)}`}>
              {fmtPct(metrics.total_return_pct)}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Alpaca Connection</span>
            <span className={`font-mono text-[11px] ${alpacaConnected ? 'text-[#00ff88]' : 'text-amber-400'}`}>
              {alpacaConnected ? '● Connected (paper)' : '○ Not configured'}
            </span>
          </div>
        </div>

        <div className="rounded-[12px] bg-amber-400/10 border border-amber-400/20 px-4 py-3 text-xs text-amber-300 leading-relaxed">
          {alpacaConnected
            ? 'A market order will be submitted to your Alpaca paper account. No real capital will be used.'
            : 'Alpaca credentials not configured — the strategy will be queued in Fund OS only. To enable live paper orders, add ALPACA_API_KEY and ALPACA_SECRET_KEY to the backend environment.'}
        </div>

        <div className="flex gap-3">
          <Button onClick={onDeploy} className="flex-1 h-11 rounded-full font-semibold">
            <Play className="w-4 h-4 mr-2" /> Confirm Deploy
          </Button>
          <Button variant="outline" onClick={onCancel} className="flex-1 h-11 rounded-full border-white/10">
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

const PIPELINE_STEPS = [
  { id: 'init', label: 'Initialize' },
  { id: 'macro', label: 'Macro Regime' },
  { id: 'market_data', label: 'Market Data' },
  { id: 'swarm', label: 'Strategy Swarm' },
  { id: 'backtest', label: 'Backtesting' },
  { id: 'evaluate', label: 'Evaluation' },
  { id: 'report', label: 'Report' },
];

const STEP_INDEX = Object.fromEntries(PIPELINE_STEPS.map((s, i) => [s.id, i]));

export default function QuantAgent() {
  const navigate = useNavigate();

  // ── input state ──
  const [ticker, setTicker] = useState('NVDA');
  const [capital, setCapital] = useState('100000');
  const [riskProfile, setRiskProfile] = useState('balanced');

  // ── run state ──
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [currentStepIdx, setCurrentStepIdx] = useState(-1);
  const [stepMessages, setStepMessages] = useState({});
  const [report, setReport] = useState(null);
  const [backtests, setBacktests] = useState({});
  const [activeBacktest, setActiveBacktest] = useState(null);
  const [showDeploy, setShowDeploy] = useState(false);
  const [deployDone, setDeployDone] = useState(false);

  // ── Alpaca status ──
  const [alpacaStatus, setAlpacaStatus] = useState(null); // null = unknown

  const abortRef = useRef(null);

  // Abort any in-flight SSE stream when the component unmounts
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  // Fetch Alpaca connectivity status once on mount
  useEffect(() => {
    const token = localStorage.getItem('mf_token');
    if (!token) return;
    fetch(`${API_BASE}/api/fundos/alpaca/status`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setAlpacaStatus(data); })
      .catch(() => {});
  }, []);

  const handleEvent = useCallback((evt) => {
    const { type } = evt;

    if (type === 'step') {
      const idx = STEP_INDEX[evt.step] ?? -1;
      setCurrentStepIdx(idx);
      setStepMessages(prev => ({ ...prev, [evt.step]: evt.message }));
    } else if (type === 'backtest') {
      setBacktests(prev => ({ ...prev, [evt.strategy_id]: evt }));
      setActiveBacktest(aid => aid || evt.strategy_id);
    } else if (type === 'done') {
      setCurrentStepIdx(PIPELINE_STEPS.length);
      if (evt.report) {
        setReport(evt.report);
        const fullBts = evt.report.backtests || {};
        setBacktests(prev => {
          const merged = { ...prev };
          for (const [id, bt] of Object.entries(fullBts)) {
            merged[id] = { ...(merged[id] || {}), ...bt };
          }
          return merged;
        });
        setActiveBacktest(evt.report.best_strategy_id || null);
      }
    } else if (type === 'error') {
      setError(evt.message || 'Unknown error');
    }
  }, []);

  const handleRun = useCallback(async () => {
    const t = ticker.trim().toUpperCase();
    if (!t) return;

    setRunning(true);
    setError(null);
    setReport(null);
    setBacktests({});
    setActiveBacktest(null);
    setCurrentStepIdx(0);
    setStepMessages({});
    setDeployDone(false);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const token = localStorage.getItem('mf_token');
      const res = await fetch(`${API_BASE}/api/fundos/quant-agent/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          ticker: t,
          capital: parseFloat(capital) || 100000,
          risk_profile: riskProfile,
        }),
        signal: ctrl.signal,
      });

      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep partial line

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            handleEvent(evt);
          } catch {
            // ignore parse errors
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Research failed');
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }, [ticker, capital, riskProfile, handleEvent]);

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const handleExport = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `quant-report-${report.ticker}-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDeploy = async () => {
    setShowDeploy(false);
    setDeployDone(true);

    // If Alpaca is connected, submit a market order to the paper account.
    // Use qty=1 as a safe, unambiguous default — the user can adjust in Alpaca directly.
    if (alpacaStatus?.configured && report) {
      try {
        const token = localStorage.getItem('mf_token');
        const t = ticker.trim().toUpperCase();
        await fetch(`${API_BASE}/api/fundos/alpaca/order`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            symbol: t,
            qty: 1,
            side: 'buy',
            order_type: 'market',
            time_in_force: 'day',
            strategy_id: report.best_strategy_id || 'quant-agent',
            approved: true,
          }),
        });
      } catch (_) {
        // Non-blocking — order attempt failure should not block navigation
      }
    }

    navigate('/fund-os');
  };

  // ── derived ──
  const activebt = activeBacktest ? backtests[activeBacktest] : null;
  const metrics = activebt?.metrics || {};
  const benchMetrics = activebt?.benchmark_metrics || {};
  const equityCurve = activebt?.equity_curve || [];
  const drawdownSeries = activebt?.drawdown_series || [];
  const monthlyReturns = activebt?.monthly_returns || [];
  const tradeLog = activebt?.trade_log || [];

  const stepsWithMessages = PIPELINE_STEPS.map(s => ({
    ...s,
    message: stepMessages[s.id] || '',
  }));

  return (
    <div className="p-4 md:p-6 lg:p-8">
      <div className="mx-auto max-w-7xl space-y-6">

        {/* ── Header ── */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="rounded-full bg-primary/10 border border-primary/20 px-3 py-1 flex items-center gap-2 text-[11px] font-mono uppercase tracking-[0.2em] text-primary">
              <FlaskConical className="w-3.5 h-3.5" />
              Quant Agent
            </div>
            <div className="text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground border border-white/8 rounded-full px-3 py-1">
              Autonomous Research Engine
            </div>
            {/* Alpaca connection badge */}
            {alpacaStatus !== null && (
              <div className={`text-[11px] font-mono uppercase tracking-[0.14em] border rounded-full px-3 py-1 flex items-center gap-1.5 ${
                alpacaStatus.configured
                  ? 'border-[#00ff88]/30 text-[#00ff88] bg-[#00ff88]/5'
                  : 'border-amber-400/30 text-amber-400 bg-amber-400/5'
              }`}>
                <span className="text-[8px]">{alpacaStatus.configured ? '●' : '○'}</span>
                Alpaca {alpacaStatus.configured ? 'Connected' : 'Not configured'}
              </div>
            )}
          </div>
          <h1 className="text-3xl md:text-4xl font-semibold text-foreground leading-tight">
            Autonomous Quant Research
          </h1>
          <p className="text-muted-foreground max-w-2xl leading-relaxed">
            Fully autonomous pipeline: macro analysis → multi-agent strategy swarm → multi-strategy backtest → performance report.
            Review results and optionally deploy to paper trading. No real capital is touched without your explicit approval.
          </p>
        </div>

        {/* ── Input form ── */}
        <Card className="rounded-[24px] border-white/10 bg-card/60 backdrop-blur-sm">
          <CardContent className="p-6">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

              <div className="space-y-1.5">
                <label className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Ticker</label>
                <input
                  value={ticker}
                  onChange={e => setTicker(e.target.value.toUpperCase())}
                  placeholder="e.g. NVDA"
                  className="w-full h-11 rounded-[12px] border border-white/10 bg-white/5 px-4 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Capital ($)</label>
                <input
                  type="number"
                  value={capital}
                  onChange={e => setCapital(e.target.value)}
                  placeholder="100000"
                  className="w-full h-11 rounded-[12px] border border-white/10 bg-white/5 px-4 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Risk Profile</label>
                <select
                  value={riskProfile}
                  onChange={e => setRiskProfile(e.target.value)}
                  className="w-full h-11 rounded-[12px] border border-white/10 bg-[#0d1117] px-4 font-mono text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                >
                  {RISK_PROFILES.map(p => (
                    <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                  ))}
                </select>
              </div>

              <div className="flex items-end">
                {running ? (
                  <Button onClick={handleStop} variant="outline" className="h-11 w-full rounded-full border-destructive/30 text-destructive hover:bg-destructive/10">
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> Stop
                  </Button>
                ) : (
                  <Button onClick={handleRun} className="h-11 w-full rounded-full font-semibold" disabled={!ticker.trim()}>
                    <Sparkles className="w-4 h-4 mr-2" /> Run Research
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {error && (
          <div className="rounded-[16px] border border-destructive/30 bg-destructive/10 px-4 py-3 flex items-center gap-3 text-sm text-destructive">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* ── Main layout ── */}
        {(running || report || Object.keys(backtests).length > 0) && (
          <div className="grid gap-6 lg:grid-cols-[280px_1fr]">

            {/* ── Pipeline progress sidebar ── */}
            <div className="space-y-4">
              <Card className="rounded-[20px] border-white/8 bg-card/60">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-sm font-mono uppercase tracking-wider text-muted-foreground">
                    <Activity className="w-4 h-4 text-primary" />
                    Research Pipeline
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <StepIndicator steps={stepsWithMessages} currentStep={currentStepIdx} />
                </CardContent>
              </Card>

              {/* Quick snapshot */}
              {report?.snapshot && (
                <Card className="rounded-[20px] border-white/8 bg-card/60">
                  <CardContent className="p-4 space-y-3">
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Snapshot</div>
                    <div className="space-y-1.5 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Price</span>
                        <span className="font-mono text-foreground">{report.snapshot.price ? `$${fmt2(report.snapshot.price)}` : '--'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Change</span>
                        <span className={`font-mono ${METRIC_COLOR(report.snapshot.change_pct)}`}>
                          {fmtPct(report.snapshot.change_pct)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Sector</span>
                        <span className="font-mono text-foreground text-right max-w-[130px] truncate">{report.snapshot.sector || '--'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">P/E</span>
                        <span className="font-mono">{report.snapshot.pe_ratio ? fmt2(report.snapshot.pe_ratio) : '--'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Trend</span>
                        <span className={`font-mono capitalize ${
                          report.snapshot.trend === 'bullish' ? 'text-[#00ff88]' :
                          report.snapshot.trend === 'bearish' ? 'text-[#ff4444]' : 'text-muted-foreground'
                        }`}>{report.snapshot.trend || '--'}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Macro regime */}
              {report?.macro && (
                <Card className="rounded-[20px] border-white/8 bg-card/60">
                  <CardContent className="p-4 space-y-2">
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">Macro Regime</div>
                    <div className="text-sm font-mono text-primary capitalize">{report.macro.regime || 'unknown'}</div>
                    <div className="text-xs text-muted-foreground leading-relaxed">{report.macro.summary || ''}</div>
                    {report.macro.confidence && (
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 rounded-full bg-white/8 overflow-hidden">
                          <div className="h-full bg-primary rounded-full" style={{ width: `${report.macro.confidence}%` }} />
                        </div>
                        <span className="text-[11px] font-mono text-muted-foreground">{report.macro.confidence}%</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>

            {/* ── Main content area ── */}
            <div className="space-y-6">

              {/* Strategy selector tabs */}
              {Object.keys(backtests).length > 0 && (
                <div className="flex flex-wrap gap-2 items-center">
                  <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground mr-1">Strategy:</span>
                  {Object.keys(backtests).map(sid => (
                    <button key={sid} onClick={() => setActiveBacktest(sid)}>
                      <StrategyBadge stratId={sid} active={activeBacktest === sid} />
                    </button>
                  ))}
                  {report?.best_strategy_id && (
                    <span className="text-[11px] font-mono text-primary ml-2">
                      ★ Best: {STRATEGY_LABELS[report.best_strategy_id] || report.best_strategy_id}
                    </span>
                  )}
                </div>
              )}

              {/* Performance metrics grid */}
              {activebt && (
                <Card className="rounded-[24px] border-white/8 bg-card/60">
                  <CardHeader className="pb-4">
                    <div className="flex items-center justify-between flex-wrap gap-3">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <BarChart2 className="w-4 h-4 text-primary" />
                        Performance Metrics
                        <span className="text-sm font-normal text-muted-foreground ml-1">
                          — {activebt.strategy_name || STRATEGY_LABELS[activeBacktest]}
                        </span>
                      </CardTitle>
                      <div className="text-xs font-mono text-muted-foreground">
                        vs Buy &amp; Hold: {fmtPct(benchMetrics.total_return_pct)}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
                      <MetricCard
                        label="Total Return"
                        value={metrics.total_return_pct !== undefined ? `${fmtPct(metrics.total_return_pct)}` : null}
                        colorFn={() => METRIC_COLOR(metrics.total_return_pct)}
                      />
                      <MetricCard
                        label="Ann. Return"
                        value={metrics.annualized_return_pct !== undefined ? `${fmtPct(metrics.annualized_return_pct)}` : null}
                        colorFn={() => METRIC_COLOR(metrics.annualized_return_pct)}
                      />
                      <MetricCard
                        label="Sharpe Ratio"
                        value={metrics.sharpe_ratio}
                        colorFn={() => METRIC_COLOR(metrics.sharpe_ratio)}
                      />
                      <MetricCard
                        label="Max Drawdown"
                        value={metrics.max_drawdown_pct !== undefined ? `${metrics.max_drawdown_pct}%` : null}
                        colorFn={() => METRIC_COLOR(-metrics.max_drawdown_pct)}
                      />
                      <MetricCard label="Win Rate" value={metrics.win_rate_pct !== undefined ? `${metrics.win_rate_pct}%` : null} />
                      <MetricCard label="# Trades" value={metrics.num_trades} />
                      <MetricCard label="Avg Win" value={metrics.avg_win_pct !== undefined ? fmtPct(metrics.avg_win_pct) : null} colorFn={() => 'text-[#00ff88]'} />
                      <MetricCard label="Profit Factor" value={metrics.profit_factor} colorFn={() => METRIC_COLOR(metrics.profit_factor - 1)} />
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Charts */}
              {equityCurve.length > 0 && (
                <Card className="rounded-[24px] border-white/8 bg-card/60">
                  <CardContent className="p-6 space-y-6">
                    <BacktestChart data={equityCurve} title="Equity Curve (Strategy vs Buy &amp; Hold)" />
                    {drawdownSeries.length > 0 && <DrawdownChart data={drawdownSeries} />}
                    {monthlyReturns.length > 0 && <MonthlyReturnBars data={monthlyReturns} />}
                  </CardContent>
                </Card>
              )}

              {/* Swarm strategy output */}
              {report?.swarm_strategy && (
                <Card className="rounded-[24px] border-white/8 bg-card/60">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <BrainCircuit className="w-4 h-4 text-primary" />
                      AI Strategy Synthesis
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <pre className="text-xs text-muted-foreground whitespace-pre-wrap leading-relaxed font-mono max-h-64 overflow-y-auto rounded-[12px] bg-white/3 border border-white/8 p-4">
                      {report.swarm_strategy}
                    </pre>
                  </CardContent>
                </Card>
              )}

              {/* Trade log */}
              {tradeLog.length > 0 && (
                <Card className="rounded-[24px] border-white/8 bg-card/60">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <List className="w-4 h-4 text-primary" />
                      Trade Log
                      <span className="text-sm font-normal text-muted-foreground ml-1">— last {Math.min(tradeLog.length, 20)} trades</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto rounded-[14px] border border-white/8 bg-white/3">
                      <Table>
                        <TableHeader>
                          <TableRow className="border-white/8">
                            <TableHead className="text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground">Entry Date</TableHead>
                            <TableHead className="text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground">Exit Date</TableHead>
                            <TableHead className="text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground">Entry $</TableHead>
                            <TableHead className="text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground">Exit $</TableHead>
                            <TableHead className="text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground">P&amp;L %</TableHead>
                            <TableHead className="text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground">Direction</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {tradeLog.slice(-20).map((t, i) => (
                            <TableRow key={i} className="border-white/5 hover:bg-white/3 transition-colors">
                              <TableCell className="font-mono text-xs">{t.entry_date}</TableCell>
                              <TableCell className="font-mono text-xs">{t.exit_date}</TableCell>
                              <TableCell className="font-mono text-xs">${fmt2(t.entry_price)}</TableCell>
                              <TableCell className="font-mono text-xs">${fmt2(t.exit_price)}</TableCell>
                              <TableCell className={`font-mono text-xs font-semibold ${METRIC_COLOR(t.pnl_pct)}`}>
                                {fmtPct(t.pnl_pct)}
                              </TableCell>
                              <TableCell>
                                <span className={`text-[11px] font-mono uppercase rounded-full px-2 py-0.5 ${
                                  t.direction === 'LONG' ? 'bg-[#00ff88]/10 text-[#00ff88]' : 'bg-[#ff4444]/10 text-[#ff4444]'
                                }`}>{t.direction}</span>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Action bar */}
              {report && !running && (
                <div className="flex flex-wrap gap-3 items-center">
                  <Button
                    onClick={() => setShowDeploy(true)}
                    className="h-11 rounded-full px-6 font-semibold"
                    disabled={deployDone}
                  >
                    {deployDone ? (
                      <><CheckCircle2 className="w-4 h-4 mr-2 text-[#00ff88]" /> Deployed to Paper Trading</>
                    ) : (
                      <><Play className="w-4 h-4 mr-2" /> Deploy to Paper Trading</>
                    )}
                  </Button>
                  <Button variant="outline" onClick={handleExport} className="h-11 rounded-full px-6 border-white/10">
                    <Download className="w-4 h-4 mr-2" /> Export JSON
                  </Button>
                  <Button variant="ghost" onClick={() => navigate('/fund-os')} className="h-11 rounded-full px-4 text-muted-foreground hover:text-foreground">
                    View Fund OS Queue <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Empty state */}
        {!running && !report && Object.keys(backtests).length === 0 && !error && (
          <div className="rounded-[24px] border border-dashed border-white/10 bg-white/3 p-12 text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto">
              <FlaskConical className="w-8 h-8 text-primary" />
            </div>
            <div>
              <div className="text-lg font-semibold text-foreground">No research session active</div>
              <div className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">
                Enter a ticker and click <strong>Run Research</strong> to launch the autonomous quant pipeline.
                The agent will analyze macro regime, run strategy swarm, and backtest three strategy families.
              </div>
            </div>
            <div className="flex flex-wrap gap-2 justify-center">
              {['NVDA', 'AAPL', 'TSLA', 'SPY', 'MSFT'].map(t => (
                <button key={t} onClick={() => setTicker(t)}
                  className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-mono text-muted-foreground hover:text-primary hover:border-primary/30 transition-colors">
                  {t}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Alpaca account summary */}
        {alpacaStatus?.configured && alpacaStatus?.account && (
          <Card className="rounded-[24px] border-[#00ff88]/15 bg-card/60 backdrop-blur-sm">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Activity className="w-4 h-4 text-[#00ff88]" />
                Alpaca Paper Account
                <span className="text-[11px] font-mono text-[#00ff88] ml-1 border border-[#00ff88]/20 rounded-full px-2 py-0.5">PAPER</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
                <MetricCard label="Portfolio Value" value={fmtCurrency(alpacaStatus.account.portfolio_value)} />
                <MetricCard label="Cash" value={fmtCurrency(alpacaStatus.account.cash)} />
                <MetricCard label="Buying Power" value={fmtCurrency(alpacaStatus.account.buying_power)} />
                <MetricCard label="Account Status" value={alpacaStatus.account.status} />
              </div>
            </CardContent>
          </Card>
        )}

      </div>

      {/* Deploy dialog */}
      {showDeploy && (
        <DeployDialog
          ticker={ticker.toUpperCase()}
          capital={parseFloat(capital) || 100000}
          strategy={report?.best_strategy_name}
          bestBacktest={report ? backtests[report.best_strategy_id] : null}
          alpacaConnected={alpacaStatus?.configured === true}
          onDeploy={handleDeploy}
          onCancel={() => setShowDeploy(false)}
        />
      )}
    </div>
  );
}
