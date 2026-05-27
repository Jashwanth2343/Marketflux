import { useEffect, useState, useCallback } from 'react';
import { BrainCircuit, X, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';

const CAT_TONE = {
    preference: 'text-primary border-primary/30 bg-primary/10',
    constraint: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
    thesis: 'text-sky-300 border-sky-500/30 bg-sky-500/10',
    goal: 'text-violet-300 border-violet-500/30 bg-violet-500/10',
    watchlist: 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10',
    general: 'text-muted-foreground border-white/15 bg-white/[0.03]',
};

function memText(m) {
    // Tolerate Mem0 ({memory}) and fallback ({text}) shapes.
    return m.memory || m.text || m.content || '';
}

export default function CopilotMemory({ refreshSignal = 0 }) {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);

    const load = useCallback(async () => {
        try {
            const { data } = await api.get('/copilot/memory');
            const list = data?.items || data?.memories || [];
            setItems(Array.isArray(list) ? list : []);
        } catch {
            setItems([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);
    // Memory extraction runs in the background (a few seconds), so re-poll twice.
    useEffect(() => {
        if (refreshSignal > 0) {
            const t1 = setTimeout(load, 1500);
            const t2 = setTimeout(load, 5000);
            return () => { clearTimeout(t1); clearTimeout(t2); };
        }
    }, [refreshSignal, load]);

    const forget = async (id) => {
        setItems((prev) => prev.filter((m) => m.id !== id));
        try { await api.delete(`/copilot/memory/${id}`); } catch { load(); }
    };

    const clearAll = async () => {
        if (!items.length || busy) return;
        setBusy(true);
        try {
            await api.delete('/copilot/memory');
            setItems([]);
            toast.success('Memory cleared');
        } catch {
            toast.error('Could not clear memory');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="rounded-3xl border border-white/10 bg-gradient-to-b from-white/[0.03] to-transparent p-4">
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">
                    <BrainCircuit className="w-3.5 h-3.5 text-primary" /> Memory
                </div>
                {items.length > 0 && (
                    <button onClick={clearAll} disabled={busy}
                        className="flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hover:text-red-400 disabled:opacity-40">
                        {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />} Clear
                    </button>
                )}
            </div>

            {loading ? (
                <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground py-2">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" /> loading…
                </div>
            ) : items.length === 0 ? (
                <p className="text-xs text-muted-foreground leading-relaxed">
                    Nothing yet. Tell the copilot a preference — e.g. <span className="text-foreground">"I never short"</span> or
                    <span className="text-foreground"> "keep me under 10% per position"</span> — and it'll remember across sessions.
                </p>
            ) : (
                <ul className="space-y-2 max-h-64 overflow-y-auto pr-1">
                    {items.map((m) => (
                        <li key={m.id} className="group flex items-start gap-2 rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2">
                            <div className="min-w-0 flex-1">
                                <p className="text-[13px] leading-snug text-foreground/90">{memText(m)}</p>
                                {m.category && (
                                    <span className={`mt-1 inline-block rounded-full border px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-wider ${CAT_TONE[m.category] || CAT_TONE.general}`}>
                                        {m.category}
                                    </span>
                                )}
                            </div>
                            <button onClick={() => forget(m.id)} title="Forget"
                                className="flex-shrink-0 text-muted-foreground/50 opacity-0 transition-opacity hover:text-red-400 group-hover:opacity-100">
                                <X className="w-3.5 h-3.5" />
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
