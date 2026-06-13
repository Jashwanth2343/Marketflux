import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BookMarked, Loader2, RefreshCw, Plus, X, TrendingUp, TrendingDown,
  CircleDot, CheckCircle2, Ban, Plane,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import api from '@/lib/api';

const STATUS_TABS = [
  { label: 'All', value: '' },
  { label: 'Open', value: 'open' },
  { label: 'Closed', value: 'closed' },
  { label: 'Invalidated', value: 'invalidated' },
];

const GRADE_STYLES = {
  A: 'text-emerald-400 border-emerald-400/40 bg-emerald-400/10',
  B: 'text-lime-400 border-lime-400/40 bg-lime-400/10',
  C: 'text-zinc-300 border-zinc-400/30 bg-zinc-400/10',
  D: 'text-orange-400 border-orange-400/40 bg-orange-400/10',
  F: 'text-red-500 border-red-500/40 bg-red-500/10',
};

function GradeChip({ grade }) {
  if (!grade) return <span className="text-muted-foreground">—</span>;
  return (
    <span className={`inline-flex items-center justify-center w-6 h-6 rounded border font-mono text-xs font-bold ${GRADE_STYLES[grade] || GRADE_STYLES.C}`}>
      {grade}
    </span>
  );
}

function pctColor(v) {
  if (!Number.isFinite(v) || v === 0) return 'text-muted-foreground';
  return v > 0 ? 'text-green-500' : 'text-red-500';
}

function Pct({ value, signed = true }) {
  if (!Number.isFinite(value)) return <span className="text-muted-foreground">—</span>;
  return (
    <span className={`font-mono tabular-nums ${pctColor(value)}`}>
      {signed && value > 0 ? '+' : ''}{value.toFixed(2)}%
    </span>
  );
}

function StatusBadge({ status }) {
  const map = {
    open: { icon: CircleDot, cls: 'text-primary border-primary/20 bg-primary/10' },
    closed: { icon: CheckCircle2, cls: 'text-zinc-300 border-zinc-500/30 bg-zinc-500/10' },
    invalidated: { icon: Ban, cls: 'text-red-400 border-red-400/30 bg-red-400/10' },
  };
  const m = map[status] || map.open;
  const Icon = m.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-mono uppercase tracking-wider ${m.cls}`}>
      <Icon className="w-2.5 h-2.5" /> {status}
    </span>
  );
}

function StatCard({ label, value, sub, accent }) {
  return (
    <Card className="overflow-hidden" style={accent ? { borderTop: '3px solid #E3B85F' } : undefined}>
      <CardContent className="p-4 flex flex-col gap-1">
        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">{label}</div>
        <div className="text-2xl font-mono tabular-nums font-semibold">{value}</div>
        {sub ? <div className="text-[11px] text-muted-foreground">{sub}</div> : null}
      </CardContent>
    </Card>
  );
}

const EMPTY_FORM = {
  ticker: '', direction: 'long', rationale: '',
  price_target: '', invalidation_price: '', invalidation_date: '',
};

function NewThesisForm({ onCreated, onCancel }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload = {
        ticker: form.ticker.trim().toUpperCase(),
        direction: form.direction,
        rationale: form.rationale.trim(),
        agent_id: 'human',
      };
      if (form.price_target) payload.price_target = Number(form.price_target);
      if (form.invalidation_price) payload.invalidation_price = Number(form.invalidation_price);
      if (form.invalidation_date) payload.invalidation_date = form.invalidation_date;
      const res = await api.post('/ledger/theses', payload);
      onCreated(res?.data?.item);
      setForm(EMPTY_FORM);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not log the thesis.');
    } finally {
      setSaving(false);
    }
  };

  const inputCls = 'w-full bg-card border border-border rounded px-2.5 py-1.5 text-sm font-mono focus:outline-none focus:border-primary/60';

  return (
    <Card className="overflow-hidden" style={{ borderTop: '3px solid #E3B85F' }}>
      <CardContent className="p-4">
        <form onSubmit={submit} className="flex flex-col gap-3">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Ticker</label>
              <input className={inputCls} value={form.ticker} onChange={set('ticker')} placeholder="NVDA" required maxLength={10} data-testid="ledger-ticker-input" />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Direction</label>
              <select className={inputCls} value={form.direction} onChange={set('direction')}>
                <option value="long">Long</option>
                <option value="short">Short</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Target $</label>
              <input className={inputCls} value={form.price_target} onChange={set('price_target')} type="number" step="0.01" min="0" placeholder="optional" />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Stop / invalidation $</label>
              <input className={inputCls} value={form.invalidation_price} onChange={set('invalidation_price')} type="number" step="0.01" min="0" placeholder="optional" />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Expiry date</label>
              <input className={inputCls} value={form.invalidation_date} onChange={set('invalidation_date')} type="date" />
            </div>
          </div>
          <div>
            <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Rationale — why this trade exists</label>
            <textarea
              className={`${inputCls} min-h-[64px] font-sans`}
              value={form.rationale}
              onChange={set('rationale')}
              placeholder="Entry logic, the catalyst, and what would prove you wrong."
              required
              minLength={5}
              data-testid="ledger-rationale-input"
            />
          </div>
          {error ? <div className="text-xs text-red-400 font-mono">{error}</div> : null}
          <div className="flex items-center gap-2">
            <Button type="submit" size="sm" disabled={saving}
              className="gap-1 font-mono text-xs uppercase tracking-wider"
              style={{ background: 'hsl(var(--primary))', color: 'hsl(var(--primary-foreground))' }}>
              {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
              Log thesis
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={onCancel}
              className="gap-1 font-mono text-xs uppercase tracking-wider text-muted-foreground">
              <X className="w-3 h-3" /> Cancel
            </Button>
            <span className="text-[10px] text-muted-foreground font-mono">
              No expiry set = auto-graded vs SPY after 90 days. Daily closes only.
            </span>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function ThesisRow({ t, onClose, closing }) {
  const isOpen = t.status === 'open';
  const ret = isOpen ? t.unrealized_return_pct : t.return_pct;
  return (
    <div className="grid grid-cols-12 gap-2 items-center px-4 py-3 border-b border-border last:border-0 hover:bg-card/60 transition-colors text-sm">
      <div className="col-span-2 flex items-center gap-2 min-w-0">
        <Link to={`/stock/${t.ticker}`} className="font-mono font-bold text-primary hover:underline">{t.ticker}</Link>
        {t.direction === 'long'
          ? <TrendingUp className="w-3 h-3 text-green-500" />
          : <TrendingDown className="w-3 h-3 text-red-500" />}
        <span className="text-[10px] font-mono uppercase text-muted-foreground">{t.direction}</span>
      </div>
      <div className="col-span-2"><StatusBadge status={t.status} /></div>
      <div className="col-span-1 text-[11px] font-mono text-muted-foreground truncate" title={t.agent_id}>
        {t.agent_id}
      </div>
      <div className="col-span-2 text-right font-mono tabular-nums text-xs text-muted-foreground">
        {t.entry_date} @ ${Number(t.entry_price).toFixed(2)}
      </div>
      <div className="col-span-1 text-right"><Pct value={ret} /></div>
      <div className="col-span-1 text-right">
        {isOpen ? <span className="text-muted-foreground text-xs">—</span> : <Pct value={t.alpha_pp} />}
      </div>
      <div className="col-span-1 text-center"><GradeChip grade={t.grade} /></div>
      <div className="col-span-1 text-[10px] font-mono text-muted-foreground text-right truncate">
        {isOpen
          ? (t.price_target ? `T $${t.price_target}` : 'no target')
          : (t.close_reason || '')}
      </div>
      <div className="col-span-1 flex justify-end">
        {isOpen ? (
          <Button size="sm" variant="outline" disabled={closing === t.id}
            onClick={() => onClose(t.id)}
            className="h-6 px-2 text-[10px] font-mono uppercase tracking-wider">
            {closing === t.id ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Close'}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

export default function Ledger() {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [status, setStatus] = useState('');
  const [agent, setAgent] = useState('');
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [closing, setClosing] = useState('');
  const [expanded, setExpanded] = useState('');

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (status) params.status = status;
      if (agent) params.agent_id = agent;
      const [list, st] = await Promise.all([
        api.get('/ledger/theses', { params }),
        api.get('/ledger/stats'),
      ]);
      setItems(list?.data?.items || []);
      setStats(st?.data || null);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [status, agent]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const closeThesis = async (id) => {
    setClosing(id);
    try {
      await api.post(`/ledger/theses/${id}/close`);
      await fetchAll();
    } catch {
      // surfaced by refetch state; keep quiet
    } finally {
      setClosing('');
    }
  };

  const agents = useMemo(() => Object.keys(stats?.per_agent || {}), [stats]);
  const gradeCounts = stats?.grade_counts || {};

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/40 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 py-5 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3 min-w-0">
            <BookMarked className="w-6 h-6 text-primary" />
            <div className="min-w-0">
              <h1 className="text-xl font-semibold">Conviction Ledger</h1>
              <p className="text-xs text-muted-foreground">
                Every call — yours or the copilot's — recorded, then graded against SPY. No memory-holing.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/copilot">
              <Button size="sm" variant="outline" className="gap-1 font-mono text-xs uppercase tracking-wider">
                <Plane className="w-3 h-3" /> Copilot
              </Button>
            </Link>
            <Button size="sm" variant="outline" onClick={fetchAll} disabled={loading}
              className="gap-1 font-mono text-xs uppercase tracking-wider">
              {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
              Refresh
            </Button>
            <Button size="sm" onClick={() => setShowForm((v) => !v)}
              className="gap-1 font-mono text-xs uppercase tracking-wider"
              style={{ background: 'hsl(var(--primary))', color: 'hsl(var(--primary-foreground))' }}
              data-testid="ledger-new-thesis-btn">
              <Plus className="w-3 h-3" /> New thesis
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-6 flex flex-col gap-5">
        {showForm ? (
          <NewThesisForm
            onCreated={() => { setShowForm(false); fetchAll(); }}
            onCancel={() => setShowForm(false)}
          />
        ) : null}

        {/* Scoreboard */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard accent label="Hit rate"
            value={stats?.hit_rate_pct != null ? `${stats.hit_rate_pct}%` : '—'}
            sub="graded A/B vs decisive calls (C = push)" />
          <StatCard label="Avg alpha / call"
            value={stats?.avg_alpha_pp != null ? `${stats.avg_alpha_pp > 0 ? '+' : ''}${stats.avg_alpha_pp}pp` : '—'}
            sub="vs SPY over each thesis window" />
          <StatCard label="Open" value={stats?.open ?? '—'} sub={`${stats?.total ?? 0} total theses`} />
          <StatCard label="Graded"
            value={stats?.graded ?? '—'}
            sub={['A', 'B', 'C', 'D', 'F'].map((g) => `${g}:${gradeCounts[g] ?? 0}`).join(' ')} />
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mr-1">status</span>
          {STATUS_TABS.map((s) => (
            <button key={s.value} type="button" onClick={() => setStatus(s.value)}
              className={`text-xs font-mono uppercase tracking-wider px-3 py-1 rounded border transition-colors ${
                status === s.value
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-card text-muted-foreground border-border hover:text-foreground'
              }`}>
              {s.label}
            </button>
          ))}
          {agents.length > 1 ? (
            <>
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground ml-3 mr-1">agent</span>
              {['', ...agents].map((a) => (
                <button key={a || 'all'} type="button" onClick={() => setAgent(a)}
                  className={`text-xs font-mono px-3 py-1 rounded border transition-colors ${
                    agent === a
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-card text-muted-foreground border-border hover:text-foreground'
                  }`}>
                  {a || 'all'}
                </button>
              ))}
            </>
          ) : null}
        </div>

        {/* Table */}
        <Card className="overflow-hidden">
          <div className="grid grid-cols-12 gap-2 items-center px-4 py-2 border-b border-border bg-muted/40 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            <div className="col-span-2">ticker</div>
            <div className="col-span-2">status</div>
            <div className="col-span-1">agent</div>
            <div className="col-span-2 text-right">entry</div>
            <div className="col-span-1 text-right">return</div>
            <div className="col-span-1 text-right">alpha</div>
            <div className="col-span-1 text-center">grade</div>
            <div className="col-span-1 text-right">note</div>
            <div className="col-span-1" />
          </div>
          {loading && items.length === 0 ? (
            <div className="px-4 py-12 text-center text-xs text-muted-foreground">Loading…</div>
          ) : items.length === 0 ? (
            <div className="px-4 py-12 text-center text-xs text-muted-foreground">
              No theses yet. Log one manually, or let the copilot earn its first entry — any turn where it
              scores a name (|composite| ≥ 30) and sizes the trade is recorded automatically.
            </div>
          ) : (
            items.map((t) => (
              <div key={t.id}>
                <div onClick={() => setExpanded(expanded === t.id ? '' : t.id)} className="cursor-pointer">
                  <ThesisRow t={t} onClose={closeThesis} closing={closing} />
                </div>
                {expanded === t.id ? (
                  <div className="px-6 py-3 bg-muted/20 border-b border-border text-xs text-muted-foreground whitespace-pre-wrap">
                    <div className="font-mono uppercase tracking-wider text-[10px] mb-1 text-primary">Rationale</div>
                    {t.rationale}
                    {t.benchmark_return_pct != null ? (
                      <div className="mt-2 font-mono text-[11px]">
                        SPY over window: <Pct value={t.benchmark_return_pct} /> · closed {t.close_date} @ ${t.close_price}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ))
          )}
        </Card>

        <p className="text-[11px] text-muted-foreground text-center pt-2 pb-8">
          Theses are graded on daily adjusted closes against SPY. Paper research record — not investment advice.
        </p>
      </div>
    </div>
  );
}
