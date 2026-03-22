import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Command, ArrowRight } from 'lucide-react';
import api from '@/lib/api';
import { cn } from '@/lib/utils';

export default function SearchBar({ variant = 'default', className = '' }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(-1);
  const [loading, setLoading] = useState(false);
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
    if (!q || q.length < 1) {
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
    setSelectedIdx(-1);
    setOpen(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 300);
  };

  const handleSelect = (item) => {
    if (typeof item === 'string') {
      navigate(`/stock/${item}`);
    } else if (item.kind === 'strategy') {
      // Just route to fund-os for now, or could have a modal
      navigate(`/fund-os?strategy=${item.id}`);
    } else {
      navigate(`/stock/${item.symbol || item}`);
    }
    setOpen(false);
    setQuery('');
    setResults([]);
  };

  const handleKeyDown = (e) => {
    if (!open || results.length === 0) {
      if (e.key === 'Enter' && query.trim()) {
        handleSelect(query.trim().toUpperCase());
      }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIdx((prev) => Math.min(prev + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIdx((prev) => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIdx >= 0 && results[selectedIdx]) {
        handleSelect(results[selectedIdx].symbol);
      } else if (query.trim()) {
        handleSelect(query.trim().toUpperCase());
      }
    }
  };

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
          placeholder={isHero ? "Search tickers, issuers, sectors, or macro themes..." : "Search by company name or ticker..."}
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

      {open && query.length > 0 && (
        <div
          data-testid="search-dropdown"
          className={cn(
            'absolute top-full left-0 right-0 z-50 max-h-80 overflow-y-auto shadow-lg shadow-black/30',
            isHero ? 'mt-3 rounded-[22px] border border-primary/15 bg-card/95 backdrop-blur-xl' : 'mt-1 bg-card border border-border'
          )}
        >
          {loading && (
            <div className="px-4 py-3 text-xs font-mono text-muted-foreground">Searching...</div>
          )}

          {!loading && results.length > 0 && (
            <>
              <div className="px-4 py-1.5 text-[10px] font-mono text-muted-foreground uppercase tracking-wider border-b border-border dark:bg-muted/20 bg-muted">
                Symbols
              </div>
              {results.map((result, idx) => (
                <button
                  key={`${result.id || result.symbol}-${idx}`}
                  data-testid={`search-result-${result.id || result.symbol}`}
                  onClick={() => handleSelect(result)}
                  className={`w-full px-4 py-2.5 text-left flex items-center justify-between transition-colors ${
                    idx === selectedIdx ? 'bg-primary/10 border-l-2 border-l-primary' : 'hover:dark:bg-muted/50 hover:bg-muted border-l-2 border-l-transparent'
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={cn("font-mono text-sm font-bold", result.kind === 'strategy' ? "text-[#00ff88]" : "text-primary")}>
                        {result.kind === 'strategy' ? result.title : result.symbol}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">{result.kind === 'strategy' ? `Strategy for ${result.ticker} • ${result.status}` : result.name}</p>
                  </div>
                  <div className="text-right flex-shrink-0 ml-4">
                    <span className="text-[10px] font-mono text-muted-foreground block">{result.kind === 'strategy' ? 'Strategy' : (result.type || 'Equity')}</span>
                    <span className="text-[10px] font-mono text-muted-foreground/60">{result.kind === 'strategy' ? `${result.confidence}/100` : result.exchange}</span>
                  </div>
                </button>
              ))}
            </>
          )}

          {!loading && results.length === 0 && query.length > 0 && (
            <button
              onClick={() => handleSelect(query.trim().toUpperCase())}
              className="w-full px-4 py-3 text-left hover:dark:bg-muted/50 hover:bg-muted transition-colors flex items-center gap-3"
            >
              <ArrowRight className="w-4 h-4 text-primary" />
              <span className="text-sm font-mono text-foreground">
                Go to <span className="text-primary font-bold">{query.trim().toUpperCase()}</span>
              </span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
