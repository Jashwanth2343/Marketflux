import { useState, useRef, useMemo, useCallback, useEffect } from 'react';
import {
  ChevronRight, Zap, MessageCircle, Search, CornerDownLeft, HelpCircle, Filter,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { FUNCTIONS, findFunction } from './functions';

/* The terminal function line. Bloomberg-style function codes (RES, N, SCR, MAC,
   TH) AND plain English in one input, AI-routed:
     NVDA            → focus the security + AI tape-read
     why TSLA        → grounded AI read with sources
     semis under 15 PE → natural-language screen
     should I hedge? → hand off to the copilot
   Keyboard: ↑/↓ pick a suggestion or recall history · ↵ run · Esc clear. */

const TICKER_RE = /^[A-Za-z][A-Za-z.\-^]{0,5}$/;
const WHY_RE = /^(?:why|read)\s+([A-Za-z][A-Za-z.\-^]{0,5})$/i;
const ASK_RE = /^(?:ask|@)\s*(.{2,})$/i;
const SCREEN_RE = /\b(screen|stocks?|tickers?|companies|names?|under|over|below|above|p\/?e|market\s?cap|dividend|yield|growth|cheap|undervalued|overvalued|sector|cap\b)\b/i;

/** Parse raw input into a single primary intent. */
function parseIntent(raw) {
  const t = raw.trim();
  if (!t) return { type: 'empty' };
  if (/^(help|h|\?)$/i.test(t)) return { type: 'help' };

  const why = WHY_RE.exec(t);
  if (why) return { type: 'read', ticker: why[1].toUpperCase() };

  const ask = ASK_RE.exec(t);
  if (ask) return { type: 'ask', text: ask[1].trim() };

  const fn = findFunction(t);
  if (fn) return { type: 'function', fn };

  if (TICKER_RE.test(t)) return { type: 'ticker', ticker: t.toUpperCase() };

  // Multi-word free text → screen vs. ask the copilot.
  if (SCREEN_RE.test(t)) return { type: 'screen', query: t };
  return { type: 'ask', text: t };
}

function intentPreview(intent) {
  switch (intent.type) {
    case 'help': return { icon: HelpCircle, run: 'Show command help', tone: 'muted' };
    case 'read': return { icon: Zap, run: <>AI tape-read <b className="text-primary">{intent.ticker}</b> — grounded, with sources</>, tone: 'primary' };
    case 'ask': return { icon: MessageCircle, run: <>Ask the copilot: <span className="text-primary">“{intent.text}”</span></>, tone: 'primary' };
    case 'function': return { icon: intent.fn.icon, run: <>Open <b className="text-primary">{intent.fn.label}</b> — {intent.fn.desc}</>, tone: 'primary' };
    case 'ticker': return { icon: Search, run: <>Focus <b className="text-primary">{intent.ticker}</b> + AI tape-read</>, tone: 'primary' };
    case 'screen': return { icon: Filter, run: <>Screen: <span className="text-primary">“{intent.query}”</span></>, tone: 'primary' };
    default: return null;
  }
}

export default function CommandLine({ onFunction, onRead, onAsk, onScreen, onFocus }) {
  const [value, setValue] = useState('');
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(0);
  const [histIdx, setHistIdx] = useState(-1);
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const historyRef = useRef([]); // most-recent-first

  // Global "/" focuses the command line (ignored while typing in a field).
  useEffect(() => {
    const onKey = (e) => {
      const tag = (e.target?.tagName || '').toLowerCase();
      const typing = tag === 'input' || tag === 'textarea' || e.target?.isContentEditable;
      if (e.key === '/' && !typing) {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    const onDown = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  const intent = useMemo(() => parseIntent(value), [value]);

  // Suggestion list: the parsed intent first, then matching function codes.
  const items = useMemo(() => {
    const out = [];
    if (intent.type !== 'empty') out.push({ kind: 'intent', intent });
    const q = value.trim().toLowerCase();
    const fnMatches = q.length === 0
      ? FUNCTIONS
      : FUNCTIONS.filter((f) => f.code.toLowerCase().startsWith(q) || f.aliases.some((a) => a.startsWith(q)) || f.label.toLowerCase().includes(q));
    for (const f of fnMatches) {
      if (intent.type === 'function' && intent.fn.code === f.code) continue; // already the primary
      out.push({ kind: 'function', fn: f });
    }
    return out;
  }, [intent, value]);

  const run = useCallback((it) => {
    let act = it;
    if (!act) act = items[selected] || items[0];
    if (!act) return;
    const fire = (intentObj) => {
      switch (intentObj.type) {
        case 'help': onFunction?.('__help__'); break;
        case 'function': onFunction?.(intentObj.fn.tab); break;
        case 'read': onRead?.(intentObj.ticker); break;
        case 'ticker': onFocus?.(intentObj.ticker); onRead?.(intentObj.ticker); break;
        case 'ask': onAsk?.(intentObj.text); break;
        case 'screen': onScreen?.(intentObj.query); break;
        default: break;
      }
    };
    if (act.kind === 'function') fire({ type: 'function', fn: act.fn });
    else fire(act.intent);

    const trimmed = value.trim();
    if (trimmed) historyRef.current = [trimmed, ...historyRef.current.filter((h) => h !== trimmed)].slice(0, 30);
    setValue('');
    setOpen(false);
    setSelected(0);
    setHistIdx(-1);
  }, [items, selected, value, onFunction, onRead, onAsk, onScreen, onFocus]);

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelected((p) => Math.min(p + 1, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      // At the top of the list, recall command history.
      if (selected <= 0 && historyRef.current.length) {
        const next = Math.min(histIdx + 1, historyRef.current.length - 1);
        setHistIdx(next);
        setValue(historyRef.current[next]);
        setOpen(true);
      } else {
        setSelected((p) => Math.max(p - 1, 0));
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      run();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      if (value) { setValue(''); setHistIdx(-1); } else { setOpen(false); inputRef.current?.blur(); }
    }
  };

  return (
    <div ref={containerRef} className="relative" data-testid="terminal-command-line">
      <div className="relative flex items-center">
        <ChevronRight className="absolute left-3 w-4 h-4 text-primary" aria-hidden="true" />
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls="command-suggestions"
          aria-label="Terminal command line"
          autoComplete="off"
          spellCheck="false"
          data-testid="command-input"
          value={value}
          onChange={(e) => { setValue(e.target.value); setOpen(true); setSelected(0); setHistIdx(-1); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder='Command — "RES" · "NVDA" · "why TSLA" · "semis under 15 PE" · "should I hedge?"'
          className="w-full bg-background border border-border rounded-lg pl-9 pr-16 py-3 font-mono text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/30 transition-colors"
        />
        <kbd className="absolute right-3 hidden sm:flex items-center gap-1 text-[10px] font-mono text-muted-foreground border border-border bg-muted rounded px-1.5 py-0.5">
          <CornerDownLeft className="w-3 h-3" /> run
        </kbd>
      </div>

      {open && items.length > 0 && (
        <div
          id="command-suggestions"
          role="listbox"
          data-testid="command-suggestions"
          className="absolute top-full left-0 right-0 z-50 mt-1.5 max-h-80 overflow-y-auto bg-card border border-border rounded-lg shadow-lg shadow-black/30"
        >
          {items.map((it, idx) => {
            const active = idx === selected;
            const base = cn('w-full px-3 py-2.5 flex items-center gap-3 text-left transition-colors', active ? 'bg-primary/10' : 'hover:bg-muted/50');
            if (it.kind === 'intent') {
              const pv = intentPreview(it.intent);
              if (!pv) return null;
              const Icon = pv.icon;
              return (
                <button key="intent" role="option" aria-selected={active} className={base} onClick={() => run(it)} data-testid="cmd-primary-intent">
                  <Icon className="w-4 h-4 text-primary flex-shrink-0" />
                  <span className="text-sm text-foreground flex-1 truncate">{pv.run}</span>
                  <span className="text-[10px] font-mono text-muted-foreground/60 uppercase tracking-wide">↵ run</span>
                </button>
              );
            }
            const Icon = it.fn.icon;
            return (
              <button key={it.fn.code} role="option" aria-selected={active} className={base} onClick={() => run(it)} data-testid={`cmd-fn-${it.fn.tab}`}>
                <Icon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                <span className="font-mono text-xs font-bold text-primary w-9">{it.fn.code}</span>
                <span className="text-sm text-foreground">{it.fn.label}</span>
                <span className="text-xs text-muted-foreground truncate flex-1">— {it.fn.desc}</span>
              </button>
            );
          })}
          <div className="border-t border-border px-3 py-1.5 text-[10px] font-mono text-muted-foreground/70 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span><span className="text-primary">RES N SCR MAC TH</span> functions</span>
            <span><span className="text-primary">why TKR</span> AI read</span>
            <span><span className="text-primary">ask …</span> copilot</span>
            <span>↑↓ pick / history · ↵ run · esc clear</span>
          </div>
        </div>
      )}
    </div>
  );
}
