import { useEffect, useState, useCallback } from 'react';
import {
    Plus, Play, Pause, Trash2, Loader2, Bot, Clock, ShieldCheck, Sparkles, X,
    ArrowUpCircle, ArrowDownCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import api from '@/lib/api';

const INTERVALS = [
    { label: 'Every 15 min', value: 15 },
    { label: 'Every 30 min', value: 30 },
    { label: 'Hourly', value: 60 },
    { label: 'Every 4 hours', value: 240 },
    { label: 'Daily', value: 1440 },
];

const EXAMPLES = [
    'Every hour, trim any position up more than 12% by selling a third of it.',
    'Each run, if any watchlist name has RSI under 30, buy $2,000 of the best setup.',
    'If my tech exposure exceeds 40% of equity, hedge by trimming the weakest name.',
];

function fmtTime(iso) {
    if (!iso) return '—';
    try { return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
    catch { return iso; }
}

function intervalLabel(min) {
    const f = INTERVALS.find((i) => i.value === min);
    return f ? f.label : `Every ${min} min`;
}

function TradeChip({ t }) {
    const buy = t.side === 'buy';
    const Icon = t.action === 'order' ? (buy ? ArrowUpCircle : ArrowDownCircle) : null;
    const label = t.action === 'cancel_all' ? 'cancelled orders'
        : t.action === 'close' ? `closed ${t.symbol}`
            : `${buy ? 'bought' : 'sold'} ${t.qty} ${t.symbol}`;
    return (
        <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-mono ${buy ? 'border-primary/30 text-primary' : 'border-amber-500/30 text-amber-400'}`}>
            {Icon && <Icon className="w-3 h-3" />}{label}{t.pending ? ' (pending)' : ''}
        </span>
    );
}

export default function StandingAgents() {
    const [agents, setAgents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [creating, setCreating] = useState(false);
    const [busy, setBusy] = useState(null);
    const [form, setForm] = useState({ name: '', instruction: '', interval_minutes: 60 });

    const load = useCallback(async () => {
        try { const { data } = await api.get('/copilot/agents'); setAgents(data?.items || []); }
        catch { setAgents([]); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { load(); }, [load]);

    const create = async () => {
        if (!form.name.trim() || form.instruction.trim().length < 5) { toast.error('Add a name and an instruction'); return; }
        setCreating(true);
        try {
            await api.post('/copilot/agents', form);
            toast.success('Standing agent created');
            setForm({ name: '', instruction: '', interval_minutes: 60 });
            setShowForm(false);
            load();
        } catch (e) { toast.error(e?.response?.data?.detail || 'Could not create agent'); }
        finally { setCreating(false); }
    };

    const runNow = async (id) => {
        setBusy(id);
        try {
            const { data } = await api.post(`/copilot/agents/${id}/run`);
            toast.success('Agent ran', { description: (data?.run?.summary || '').slice(0, 90) });
            load();
        } catch { toast.error('Run failed'); }
        finally { setBusy(null); }
    };

    const toggle = async (a) => {
        try { await api.put(`/copilot/agents/${a.id}`, { status: a.status === 'active' ? 'paused' : 'active' }); load(); }
        catch { toast.error('Could not update'); }
    };

    const remove = async (id) => {
        setAgents((prev) => prev.filter((a) => a.id !== id));
        try { await api.delete(`/copilot/agents/${id}`); } catch { load(); }
    };

    return (
        <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-5">
                <div>
                    <h3 className="flex items-center gap-2 text-lg font-semibold text-foreground">
                        <Bot className="w-5 h-5 text-primary" /> Standing Agents
                    </h3>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Saved instructions the copilot runs on a schedule — autonomously, on your paper account.
                    </p>
                </div>
                <Button onClick={() => setShowForm((s) => !s)} className="rounded-xl gap-1.5">
                    {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}{showForm ? 'Close' : 'New agent'}
                </Button>
            </div>

            <div className="mb-4 flex items-center gap-1.5 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-3 py-2 text-xs font-mono text-amber-300/90">
                <ShieldCheck className="w-3.5 h-3.5 flex-shrink-0" />
                Standing agents execute autonomously (no per-trade confirmation). Paper only — no real money.
            </div>

            {showForm && (
                <div className="mb-5 rounded-2xl border border-white/10 bg-white/[0.03] p-4 space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
                    <input
                        value={form.name}
                        onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                        placeholder="Agent name — e.g. Momentum Trimmer"
                        className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-foreground outline-none focus:border-primary/30"
                    />
                    <textarea
                        value={form.instruction}
                        onChange={(e) => setForm((f) => ({ ...f, instruction: e.target.value }))}
                        rows={3}
                        placeholder="What should it do each run? e.g. 'Trim any position up more than 12% by a third.'"
                        className="w-full resize-none rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-foreground outline-none focus:border-primary/30"
                    />
                    <div className="flex flex-wrap gap-1.5">
                        {EXAMPLES.map((ex) => (
                            <button key={ex} onClick={() => setForm((f) => ({ ...f, instruction: ex }))}
                                className="rounded-full border border-white/10 bg-white/[0.02] px-2.5 py-1 text-[11px] font-mono text-muted-foreground hover:border-primary/30 hover:text-foreground">
                                {ex.length > 46 ? ex.slice(0, 44) + '…' : ex}
                            </button>
                        ))}
                    </div>
                    <div className="flex items-center justify-between gap-3">
                        <select
                            value={form.interval_minutes}
                            onChange={(e) => setForm((f) => ({ ...f, interval_minutes: Number(e.target.value) }))}
                            className="h-10 rounded-xl border border-white/10 bg-white/[0.03] px-3 text-sm text-foreground outline-none"
                        >
                            {INTERVALS.map((i) => <option key={i.value} value={i.value} className="bg-popover">{i.label}</option>)}
                        </select>
                        <Button onClick={create} disabled={creating} className="rounded-xl gap-1.5">
                            {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />} Create & activate
                        </Button>
                    </div>
                </div>
            )}

            {loading ? (
                <div className="flex items-center justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
            ) : agents.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-10 text-center">
                    <Bot className="w-12 h-12 text-muted-foreground/40 mx-auto mb-3" />
                    <p className="text-sm text-muted-foreground mb-1">No standing agents yet.</p>
                    <p className="text-xs text-muted-foreground/70">Create one to have the copilot monitor and act on a schedule.</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {agents.map((a) => {
                        const lastRun = a.runs && a.runs.length ? a.runs[a.runs.length - 1] : null;
                        const active = a.status === 'active';
                        return (
                            <div key={a.id} className="rounded-2xl border border-white/10 bg-gradient-to-b from-white/[0.04] to-white/[0.01] p-4">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="min-w-0">
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold text-foreground">{a.name}</span>
                                            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider ${active ? 'border-primary/30 bg-primary/10 text-primary' : 'border-white/15 bg-white/[0.03] text-muted-foreground'}`}>
                                                {active ? 'active' : 'paused'}
                                            </span>
                                        </div>
                                        <p className="mt-1 text-sm text-muted-foreground leading-snug">{a.instruction}</p>
                                        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] font-mono text-muted-foreground/80">
                                            <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{intervalLabel(a.interval_minutes)}</span>
                                            <span>last: {fmtTime(a.last_run)}</span>
                                            {active && <span>next: {fmtTime(a.next_run)}</span>}
                                        </div>
                                    </div>
                                    <div className="flex flex-shrink-0 items-center gap-1">
                                        <Button size="sm" variant="ghost" onClick={() => runNow(a.id)} disabled={busy === a.id} className="h-8 gap-1 text-xs" title="Run now">
                                            {busy === a.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                                        </Button>
                                        <Button size="sm" variant="ghost" onClick={() => toggle(a)} className="h-8 text-xs" title={active ? 'Pause' : 'Resume'}>
                                            {active ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                                        </Button>
                                        <Button size="sm" variant="ghost" onClick={() => remove(a.id)} className="h-8 text-xs text-muted-foreground hover:text-red-400" title="Delete">
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </Button>
                                    </div>
                                </div>
                                {lastRun && (
                                    <div className="mt-3 rounded-xl border border-white/10 bg-black/20 p-3">
                                        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1">
                                            Last run · {fmtTime(lastRun.timestamp)}
                                        </div>
                                        <p className="text-[13px] text-foreground/85 leading-snug">{lastRun.summary}</p>
                                        {lastRun.trades && lastRun.trades.length > 0 && (
                                            <div className="mt-2 flex flex-wrap gap-1.5">
                                                {lastRun.trades.map((t, i) => <TradeChip key={i} t={t} />)}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
