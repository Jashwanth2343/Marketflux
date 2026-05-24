import { useEffect, useRef, useState, useCallback } from 'react';
import {
    Plane, Send, Loader2, Brain, Wrench, CheckCircle2, AlertTriangle,
    ArrowUpCircle, ArrowDownCircle, XCircle, Sparkles, ShieldCheck, Square,
    TrendingUp, Shield, Target, Zap, Activity, Cpu,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { API_BASE } from '@/lib/api';
import AccountSummary from '@/components/copilot/AccountSummary';
import CopilotMemory from '@/components/copilot/CopilotMemory';
import RichMarkdown from '@/components/RichMarkdown';

const SUGGESTIONS = [
    { text: 'Review my portfolio and tell me what to trim or add', icon: Activity },
    { text: 'Buy $5,000 of the strongest large-cap momentum name', icon: TrendingUp },
    { text: "What's my biggest risk right now, and how would you hedge it?", icon: Shield },
    { text: 'Take profit on any position up more than 10%', icon: Target },
    { text: 'Find a high-conviction swing trade for this week and execute it', icon: Zap },
];

let _mid = 0;
const nextId = () => `m${Date.now()}_${_mid++}`;

// --- activity timeline item renderers --------------------------------------
function ThinkingRow({ text }) {
    return (
        <div className="flex items-start gap-2.5 text-xs text-muted-foreground animate-in fade-in duration-300">
            <span className="mt-px flex h-4 w-4 flex-shrink-0 items-center justify-center">
                <Brain className="w-3.5 h-3.5 text-primary/70" />
            </span>
            <span className="leading-relaxed">{text}</span>
        </div>
    );
}

function ToolRow({ item }) {
    const isTrade = item.is_trade;
    const done = item.status != null;
    const failed = done && item.ok === false;
    return (
        <div className={`flex items-start gap-2.5 rounded-xl border px-3 py-2 text-xs transition-colors animate-in fade-in slide-in-from-left-1 duration-300 ${
            isTrade ? 'border-primary/30 bg-primary/[0.07]' : 'border-white/10 bg-white/[0.03]'
        }`}>
            <span className="mt-0.5 flex-shrink-0">
                {!done ? <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
                    : failed ? <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                        : <CheckCircle2 className="w-3.5 h-3.5 text-primary" />}
            </span>
            <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 font-mono text-foreground/90">
                    {isTrade && <Wrench className="w-3 h-3 text-primary" />}
                    {item.label}
                </div>
                {item.name === 'run_python' && item.args?.code && (
                    <pre className="mt-1.5 overflow-x-auto rounded-lg border border-white/10 bg-black/50 px-3 py-2 text-[11px] leading-relaxed text-emerald-300/90 whitespace-pre-wrap">
                        {item.args.code}
                    </pre>
                )}
                {done && item.summary && (
                    <div className={`mt-1 font-mono ${failed ? 'text-amber-400' : 'text-muted-foreground'}`}>
                        → {item.summary}
                    </div>
                )}
            </div>
        </div>
    );
}

function TradeCard({ t }) {
    const buy = t.side === 'buy';
    const isCancel = t.action === 'cancel_all';
    const Icon = isCancel ? XCircle : buy ? ArrowUpCircle : ArrowDownCircle;
    const tone = isCancel ? 'text-muted-foreground border-white/15 from-white/[0.04]'
        : buy ? 'text-primary border-primary/40 from-primary/15'
            : 'text-amber-400 border-amber-500/40 from-amber-500/15';
    const verb = isCancel ? 'Cancelled all open orders'
        : t.action === 'close' ? `Closed ${t.symbol}`
            : `${buy ? 'Bought' : 'Sold'} ${t.qty} ${t.symbol}`;
    return (
        <div className={`flex items-center gap-3 rounded-xl border bg-gradient-to-r to-transparent px-3.5 py-2.5 animate-in fade-in zoom-in-95 duration-300 ${tone}`}>
            <Icon className="w-5 h-5 flex-shrink-0" />
            <div className="font-mono text-sm">
                <span className="font-semibold tracking-tight">{verb}</span>
                {t.price && <span className="ml-2 opacity-80">@ ${t.price}</span>}
                {t.status && <span className="ml-2 rounded-full bg-white/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wider opacity-80">{t.status}</span>}
            </div>
        </div>
    );
}

function ActivityTimeline({ items }) {
    if (!items?.length) return null;
    return (
        <div className="relative mb-3 space-y-2 pl-4">
            <span className="absolute left-0 top-1 bottom-1 w-px bg-gradient-to-b from-primary/40 via-primary/15 to-transparent" />
            {items.map((it, i) => {
                if (it.kind === 'thinking') return <ThinkingRow key={i} text={it.message} />;
                if (it.kind === 'tool') return <ToolRow key={i} item={it} />;
                if (it.kind === 'trade') return <TradeCard key={i} t={it} />;
                return null;
            })}
        </div>
    );
}

function AgentAvatar({ size = 'sm' }) {
    const dim = size === 'lg' ? 'w-16 h-16' : 'w-8 h-8';
    const icon = size === 'lg' ? 'w-8 h-8' : 'w-4 h-4';
    return (
        <div className={`relative flex ${dim} flex-shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/25 to-primary/5 ring-1 ring-primary/30 shadow-[0_0_24px_-6px_hsl(var(--primary)/0.55)]`}>
            <Plane className={`${icon} text-primary`} />
        </div>
    );
}

export default function CopilotAgent() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [accountSignal, setAccountSignal] = useState(0);
    const [memorySignal, setMemorySignal] = useState(0);
    const sessionId = useRef(`copilot_${Date.now()}`);
    const scrollRef = useRef(null);
    const abortRef = useRef(null);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }, [messages]);

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
            const res = await fetch(`${API_BASE}/api/copilot/chat/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ message: msg, session_id: sessionId.current }),
                signal: controller.signal,
            });
            if (!res.ok || !res.body) throw new Error(`Request failed (${res.status})`);

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            const handle = (event) => {
                if (event.type === 'thinking') {
                    patchLastAssistant((m) => ({ ...m, activity: [...m.activity, { kind: 'thinking', message: event.message }] }));
                } else if (event.type === 'tool_call') {
                    patchLastAssistant((m) => ({
                        ...m,
                        activity: [...m.activity, {
                            kind: 'tool', name: event.name, label: event.label,
                            is_trade: event.is_trade, args: event.args, status: null,
                        }],
                    }));
                } else if (event.type === 'tool_result') {
                    patchLastAssistant((m) => {
                        const act = [...m.activity];
                        for (let i = act.length - 1; i >= 0; i--) {
                            if (act[i].kind === 'tool' && act[i].name === event.name && act[i].status == null) {
                                act[i] = { ...act[i], status: 'done', ok: event.ok, summary: event.summary };
                                break;
                            }
                        }
                        return { ...m, activity: act };
                    });
                } else if (event.type === 'trade') {
                    patchLastAssistant((m) => ({ ...m, activity: [...m.activity, { kind: 'trade', ...event }] }));
                    const verb = event.action === 'cancel_all' ? 'Cancelled all orders'
                        : event.action === 'close' ? `Closed ${event.symbol}`
                            : `${event.side === 'buy' ? 'Bought' : 'Sold'} ${event.qty} ${event.symbol}`;
                    toast.success(verb, { description: `Status: ${event.status || 'submitted'} · paper account` });
                    setAccountSignal((s) => s + 1);
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
                    if (!t.startsWith('data: ')) continue;
                    try { handle(JSON.parse(t.slice(6))); } catch { /* skip */ }
                }
                if (done) break;
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                patchLastAssistant((m) => ({
                    ...m, streaming: false,
                    content: m.content || `⚠ ${err.message || 'The copilot could not respond.'}`,
                }));
                toast.error(err.message || 'Copilot request failed');
            }
        } finally {
            setLoading(false);
            abortRef.current = null;
        }
    }, [input, loading, patchLastAssistant]);

    const stop = () => { abortRef.current?.abort(); abortRef.current = null; setLoading(false); patchLastAssistant((m) => ({ ...m, streaming: false })); };

    const empty = messages.length === 0;

    return (
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_352px] gap-5">
            {/* Conversation */}
            <div className="relative flex flex-col overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-b from-white/[0.04] to-white/[0.01] min-h-[680px] max-h-[82vh] shadow-2xl shadow-black/40">
                {/* Header */}
                <div className="flex items-center justify-between gap-3 border-b border-white/10 bg-white/[0.02] px-5 py-3.5">
                    <div className="flex items-center gap-3">
                        <AgentAvatar />
                        <div className="leading-tight">
                            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                                Copilot Agent
                                <span className="relative flex h-1.5 w-1.5">
                                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/70" />
                                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
                                </span>
                            </div>
                            <div className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Autonomous · Paper</div>
                        </div>
                    </div>
                    <span className="hidden sm:flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                        <ShieldCheck className="w-3.5 h-3.5" /> not advice
                    </span>
                </div>

                {/* Messages */}
                <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-5 space-y-6 scroll-smooth">
                    {empty && (
                        <div className="h-full flex flex-col items-center justify-center text-center py-8">
                            <AgentAvatar size="lg" />
                            <h3 className="mt-5 text-xl font-semibold tracking-tight bg-gradient-to-r from-foreground to-primary/80 bg-clip-text text-transparent">
                                Your autonomous trading copilot
                            </h3>
                            <p className="mt-2 text-sm text-muted-foreground max-w-md leading-relaxed">
                                It researches the market, runs the numbers, and executes paper trades on your
                                Alpaca account — and shows every step it takes.
                            </p>
                            <div className="mt-7 grid w-full max-w-xl gap-2 sm:grid-cols-2">
                                {SUGGESTIONS.map(({ text, icon: Icon }) => (
                                    <button key={text} onClick={() => send(text)}
                                        className="group flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.02] px-4 py-3 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-primary/[0.06]">
                                        <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20 transition-colors group-hover:bg-primary/20">
                                            <Icon className="w-4 h-4" />
                                        </span>
                                        <span className="text-[13px] leading-snug text-muted-foreground group-hover:text-foreground">{text}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {messages.map((m) => (
                        m.role === 'user' ? (
                            <div key={m.id} className="flex justify-end animate-in fade-in slide-in-from-right-2 duration-300">
                                <div className="max-w-[85%] rounded-2xl rounded-br-md bg-gradient-to-br from-primary/20 to-primary/10 border border-primary/25 px-4 py-2.5 text-sm text-foreground shadow-lg shadow-primary/5">
                                    {m.content}
                                </div>
                            </div>
                        ) : (
                            <div key={m.id} className="flex gap-3 animate-in fade-in slide-in-from-bottom-1 duration-300">
                                <AgentAvatar />
                                <div className="min-w-0 flex-1 pt-0.5">
                                    <ActivityTimeline items={m.activity} />
                                    {m.content ? (
                                        <RichMarkdown>{m.content}</RichMarkdown>
                                    ) : m.streaming && !m.activity?.length ? (
                                        <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
                                            <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" /> thinking…
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        )
                    ))}
                </div>

                {/* Composer */}
                <div className="border-t border-white/10 bg-white/[0.02] p-3.5">
                    {!empty && (
                        <div className="flex flex-wrap gap-1.5 mb-2.5">
                            {SUGGESTIONS.slice(0, 3).map(({ text, icon: Icon }) => (
                                <button key={text} onClick={() => send(text)} disabled={loading}
                                    className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-mono text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground disabled:opacity-40">
                                    <Icon className="w-3 h-3 text-primary/80" />
                                    {text.length > 34 ? text.slice(0, 32) + '…' : text}
                                </button>
                            ))}
                        </div>
                    )}
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] transition-all focus-within:border-primary/40 focus-within:ring-2 focus-within:ring-primary/10">
                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
                            rows={1}
                            placeholder="Tell the copilot what to research or trade…"
                            className="w-full resize-none bg-transparent px-4 pt-3 pb-1.5 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 max-h-40"
                        />
                        <div className="flex items-center justify-between px-3 pb-2.5">
                            <span className="text-[10px] font-mono text-muted-foreground/70">
                                <kbd className="rounded bg-white/10 px-1">⏎</kbd> send · <kbd className="rounded bg-white/10 px-1">⇧⏎</kbd> newline
                            </span>
                            {loading ? (
                                <Button onClick={stop} size="sm" variant="outline" className="h-8 rounded-xl border-white/15 gap-1.5">
                                    <Square className="w-3 h-3 fill-current" /> Stop
                                </Button>
                            ) : (
                                <Button onClick={() => send()} size="sm" disabled={!input.trim()} className="h-8 rounded-xl gap-1.5 shadow-lg shadow-primary/20">
                                    <Send className="w-3.5 h-3.5" /> Send
                                </Button>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Sidebar */}
            <div className="space-y-4">
                <div className="rounded-3xl border border-white/10 bg-gradient-to-b from-white/[0.04] to-white/[0.01] p-4 shadow-xl shadow-black/30">
                    <AccountSummary refreshSignal={accountSignal} source="copilot" />
                </div>
                <CopilotMemory refreshSignal={memorySignal} />
                <div className="rounded-3xl border border-white/10 bg-gradient-to-b from-white/[0.03] to-transparent p-4">
                    <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground mb-3">
                        <Sparkles className="w-3.5 h-3.5 text-primary" /> Capabilities
                    </div>
                    <ul className="space-y-2.5 text-[13px] text-muted-foreground">
                        {[
                            [TrendingUp, 'Research, buy, sell, hedge & rebalance'],
                            [Activity, 'Reads your live account before acting'],
                            [Cpu, 'Runs Python for sizing & risk math'],
                            [ShieldCheck, 'Paper trading only — no real money'],
                        ].map(([Icon, label]) => (
                            <li key={label} className="flex items-center gap-2.5">
                                <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/15">
                                    <Icon className="w-3.5 h-3.5" />
                                </span>
                                {label}
                            </li>
                        ))}
                    </ul>
                </div>
            </div>
        </div>
    );
}
