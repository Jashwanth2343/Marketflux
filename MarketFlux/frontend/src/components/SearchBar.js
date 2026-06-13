import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, Command, ArrowRight, Zap, MessageCircle, LayoutDashboard, Brain,
  Newspaper, Filter, Globe, BookMarked, FlaskConical, Briefcase, Plane, Loader2,
  TrendingUp, TrendingDown,
} from 'lucide-react';
import api from '@/lib/api';
import { cn } from '@/lib/utils';

/* The terminal line. Plain text searches symbols; `why TSLA` answers inline
   with a grounded AI read; `ask <anything>` hands off to the copilot;
   anything else fuzzy-matches navigation. */
const NAV_COMMANDS = [
  { key: 'dashboard', label: 'Dashboard', to: '/', icon: LayoutDashboard },
  { key: 'research', label: 'Research Center', to: '/intelligence?tab=research', icon: Brain },
  { key: 'news', label: 'News Feed', to: '/intelligence?tab=news', icon: Newspaper },
  { key: 'screener', label: 'AI Screener', to: '/intelligence?tab=screener', icon: Filter },
  { key: 'macro', label: 'Macro Dashboard', to: '/intelligence?tab=macro', icon: Globe },
  { key: 'copilot', label: 'Trading Copilot', to: '/copilot', icon: Plane },
  { key: 'ledger', label: 'Conviction Ledger', to: '/ledger', icon: BookMarked },
  { key: 'backtest', label: 'Backtest Lab', to: '/backtest', icon: FlaskConical },
  { key: 'portfolio', label: 'Portfolio & Risk', to: '/portfolio', icon: Briefcase },
];

const WHY_RE = /^(?:why|\?)\s+([A-Za-z.^-]{1,10})$/i;
const ASK_RE = /^(?:ask|@)\s+(.{3,})$/i;

export default function SearchBar({ variant = 'default', className = '' }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [loading, setLoading] = useState(false);
  const [explain, setExplain] = useState(null); // {status, ticker, data?, error?}
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const debounceRef = useRef(null);
  const navigate = useNavigate();
  const isHero = variant === 'hero';

  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
      if (e.key === 'Escape') {
        setOpen(false);
        inputRef.current?.blur();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const search = useCallback(async (q) => {
    if (!q || q.length < 1 || WHY_RE.test(q.trim()) || ASK_RE.test(q.trim())) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await api.get(`/fundos/search?q=${encodeURIComponent(q)}`);
      setResults(res.data.results || []);
    } catch {
      try {
        const fallbackRes = await api.get(`/search-stocks?q=${encodeURIComponent(q)}`);
        setResults(fallbackRes.data.results || []);
      } catch {
        setResults([]);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChange = (e) => {
    const val = e.target.value;
    setQuery(val);
    setSelectedIdx(0);
    setOpen(true);
    setExplain(null);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 300);
  };

  const runExplain = useCallback(async (ticker) => {
    const t = ticker.toUpperCase();
    setExplain({ status: 'loading', ticker: t });
    try {
      const { data } = await api.get(`/intelligence/explain/${t}`);
      setExplain({ status: 'done', ticker: t, data });
    } catch (err) {
      setExplain({
        status: 'error', ticker: t,
        error: err?.response?.data?.detail || 'Could not generate a read for this ticker.',
      });
    }
  }, []);

  const close = () => {
    setOpen(false);
    setQuery('');
    setResults([]);
    setExplain(null);
  };

  // One flat, keyboard-navigable item list: special actions, nav commands, symbols.
  const items = useMemo(() => {
    const trimmed = query.trim();
    const out = [];
    const why = WHY_RE.exec(trimmed);
    const ask = ASK_RE.exec(trimmed);
    if (why) {
      out.push({ kind: 'why', ticker: why[1].toUpperCase() });
      return out;
    }
    if (ask) {
      out.push({ kind: 'ask', text: ask[1] });
      return out;
    }
    const q = trimmed.toLowerCase();
    const navMatches = q.length === 0
      ? NAV_COMMANDS
      : NAV_COMMANDS.filter((c) => c.key.startsWith(q) || c.label.toLowerCase().includes(q));
    // With a short text query, symbols come first; commands trail.
    for (const r of results) out.push({ kind: 'symbol', result: r });
    for (const c of navMatches) out.push({ kind: 'nav', command: c });
    if (trimmed && results.length === 0 && !loading) {
      out.push({ kind: 'goto', ticker: trimmed.toUpperCase() });
    }
    return out;
  }, [query, results, loading]);

  const activate = (item) => {
    if (!item) return;
    if (item.kind === 'why') {
      runExplain(item.ticker);
      return; // stays open to show the read
    }
    if (item.kind === 'ask') {
      sessionStorage.setItem('copilot_ask', item.text);
      navigate('/copilot');
      close();
      return;
    }
    if (item.kind === 'nav') {
      navigate(item.command.to);
      close();
      return;
    }
    if (item.kind === 'goto') {
      navigate(`/stock/${item.ticker}`);
      close();
      return;
    }
    const r = item.result;
    if (r.kind === 'strategy') navigate(`/copilot?tab=studio&strategy=${r.id}`);
    else navigate(`/stock/${r.symbol || r}`);
    close();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIdx((prev) => Math.min(prev + 1, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIdx((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      activate(items[selectedIdx] || items[0]);
    }
  };

  const itemBase = (idx) => cn(
    'w-full px-4 py-2.5 text-left flex items-center gap-3 transition-colors',
    idx === selectedIdx ? 'bg-primary/10' : 'hover:bg-muted/50',
  );

  return (
    <div
      ref={containerRef}
      className={cn('relative w-full', isHero ? 'max-w-none' : 'max-w-lg', className)}
      data-testid="global-search-bar"
    >
      <div className="relative">
        <Search className={cn('absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground', isHero ? 'w-5 h-5 left-5' : 'w-4 h-4')} />
        <input
          ref={inputRef}
          data-testid="global-search-input"
          type="text"
          value={query}
          onChange={handleChange}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={isHero ? 'Ticker · "why NVDA" · "ask should I hedge?" · or jump anywhere' : 'Ticker · why NVDA · ask anything'}
          className={cn(
            'w-full text-foreground placeholder:text-muted-foreground/50 focus:outline-none transition-colors',
            isHero
              ? 'rounded-[22px] border border-primary/15 bg-card/80 pl-14 pr-24 py-4 text-base shadow-[0_18px_48px_rgba(0,0,0,0.18)] backdrop-blur-xl focus:border-primary/40'
              : 'pl-10 pr-16 py-2 bg-background border border-border text-sm font-mono focus:border-primary/50'
          )}
        />
        <kbd
          className={cn(
            'absolute top-1/2 -translate-y-1/2 hidden sm:flex items-center gap-0.5 text-[10px] font-mono text-muted-foreground border',
            isHero ? 'right-4 rounded-full bg-background/90 px-2.5 py-1 border-primary/15' : 'right-3 px-1.5 py-0.5 bg-muted border-border'
          )}
        >
          <Command className="w-3 h-3" />K
        </kbd>
      </div>

      {open && (
        <div
          data-testid="search-dropdown"
          className={cn(
            'absolute top-full left-0 right-0 z-50 max-h-96 overflow-y-auto shadow-lg shadow-black/30',
            isHero ? 'mt-3 rounded-[22px] border border-primary/15 bg-card/95 backdrop-blur-xl' : 'mt-1 bg-card border border-border'
          )}
        >
          {loading && (
            <div className="px-4 py-3 text-xs font-mono text-muted-foreground">Searching...</div>
          )}

          {items.map((item, idx) => {
            if (item.kind === 'why') {
              return (
                <button key="why" onClick={() => activate(item)} className={itemBase(idx)} data-testid="cmd-why">
                  <Zap className="w-4 h-4 text-primary flex-shrink-0" />
                  <span className="text-sm font-mono text-foreground">
                    Why is <span className="text-primary font-bold">{item.ticker}</span> moving? <span className="text-muted-foreground">— AI read, with sources</span>
                  </span>
                </button>
              );
            }
            if (item.kind === 'ask') {
              return (
                <button key="ask" onClick={() => activate(item)} className={itemBase(idx)} data-testid="cmd-ask">
                  <MessageCircle className="w-4 h-4 text-primary flex-shrink-0" />
                  <span className="text-sm text-foreground truncate">
                    Ask the copilot: <span className="text-primary">“{item.text}”</span>
                  </span>
                </button>
              );
            }
            if (item.kind === 'nav') {
              const Icon = item.command.icon;
              return (
                <button key={`nav-${item.command.key}`} onClick={() => activate(item)} className={itemBase(idx)} data-testid={`cmd-nav-${item.command.key}`}>
                  <Icon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  <span className="text-sm text-foreground flex-1">{item.command.label}</span>
                  <ArrowRight className="w-3 h-3 text-muted-foreground/50" />
                </button>
              );
            }
            if (item.kind === 'goto') {
              return (
                <button key="goto" onClick={() => activate(item)} className={itemBase(idx)}>
                  <ArrowRight className="w-4 h-4 text-primary flex-shrink-0" />
                  <span className="text-sm font-mono text-foreground">
                    Go to <span className="text-primary font-bold">{item.ticker}</span>
                  </span>
                </button>
              );
            }
            const r = item.result;
            return (
              <button
                key={`${r.id || r.symbol}-${idx}`}
                data-testid={`search-result-${r.id || r.symbol}`}
                onClick={() => activate(item)}
                className={itemBase(idx)}
              >
                <div className="flex-1 min-w-0">
                  <span className="font-mono text-sm font-bold text-primary">
                    {r.kind === 'strategy' ? r.title : r.symbol}
                  </span>
                  <p className="text-xs text-muted-foreground truncate">
                    {r.kind === 'strategy' ? `Strategy for ${r.ticker} • ${r.status}` : r.name}
                  </p>
                </div>
                <div className="text-right flex-shrink-0 ml-4">
                  <span className="text-[10px] font-mono text-muted-foreground block">
                    {r.kind === 'strategy' ? 'Strategy' : (r.type || 'Equity')}
                  </span>
                  <span className="text-[10px] font-mono text-muted-foreground/60">
                    {r.kind === 'strategy' ? `${r.confidence}/100` : r.exchange}
                  </span>
                </div>
              </button>
            );
          })}

          {/* Inline AI read — the answer lives in the command line itself */}
          {explain && (
            <div className="border-t border-border px-4 py-3" data-testid="explain-panel">
              {explain.status === 'loading' && (
                <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
                  Reading {explain.ticker}'s tape…
                </div>
              )}
              {explain.status === 'error' && (
                <p className="text-xs font-mono text-loss">{explain.error}</p>
              )}
              {explain.status === 'done' && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 font-mono text-sm">
                    <span className="font-bold text-primary">{explain.ticker}</span>
                    {explain.data.price != null && <span className="text-foreground">${Number(explain.data.price).toFixed(2)}</span>}
                    {explain.data.change_percent != null && (
                      <span className={cn('flex items-center gap-1 text-xs', explain.data.change_percent >= 0 ? 'text-gain' : 'text-loss')}>
                        {explain.data.change_percent >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        {explain.data.change_percent >= 0 ? '+' : ''}{explain.data.change_percent}%
                      </span>
                    )}
                  </div>
                  <p className="text-xs leading-relaxed text-foreground">{explain.data.explanation}</p>
                  {(explain.data.sources || []).length > 0 && (
                    <div className="space-y-0.5">
                      {explain.data.sources.map((s, i) => (
                        <a key={i} href={s.url || '#'} target="_blank" rel="noreferrer"
                          className="block truncate text-[11px] text-muted-foreground hover:text-primary">
                          ↳ {s.title}{s.source ? ` — ${s.source}` : ''}
                        </a>
                      ))}
                    </div>
                  )}
                  <button
                    onClick={() => { sessionStorage.setItem('copilot_ask', `Dig deeper on ${explain.ticker}: ${explain.data.explanation}`); navigate('/copilot'); close(); }}
                    className="text-[11px] font-mono text-primary hover:underline"
                  >
                    Dig deeper in Copilot →
                  </button>
                </div>
              )}
            </div>
          )}

          <div className="border-t border-border px-4 py-1.5 text-[10px] font-mono text-muted-foreground/70 flex items-center gap-3">
            <span><span className="text-primary">why TICKER</span> AI read</span>
            <span><span className="text-primary">ask …</span> copilot</span>
            <span>↑↓ navigate · ↵ select</span>
          </div>
        </div>
      )}
    </div>
  );
}
