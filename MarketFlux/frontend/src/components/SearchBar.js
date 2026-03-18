import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Command, ArrowRight } from 'lucide-react';
import api from '@/lib/api';

export default function SearchBar() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(-1);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  const debounceRef = useRef(null);
  const navigate = useNavigate();

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

  const search = useCallback(async (q) => {
    if (!q || q.length < 1) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await api.get(`/search-stocks?q=${encodeURIComponent(q)}`);
      setResults(res.data.results || []);
    } catch {
      setResults([]);
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

  const handleSelect = (symbol) => {
    navigate(`/stock/${symbol}`);
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
    <div ref={containerRef} className="relative w-full max-w-lg" data-testid="global-search-bar">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          ref={inputRef}
          data-testid="global-search-input"
          type="text"
          value={query}
          onChange={handleChange}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search by company name or ticker..."
          className="w-full pl-10 pr-16 py-2 bg-background border border-border text-sm font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/50 transition-colors"
        />
        <kbd className="absolute right-3 top-1/2 -translate-y-1/2 hidden sm:flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground bg-muted border border-border">
          <Command className="w-3 h-3" />K
        </kbd>
      </div>

      {open && query.length > 0 && (
        <div
          data-testid="search-dropdown"
          className="absolute top-full left-0 right-0 mt-1 bg-card border border-border z-50 max-h-80 overflow-y-auto shadow-lg shadow-black/50"
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
                  key={`${result.symbol}-${idx}`}
                  data-testid={`search-result-${result.symbol}`}
                  onClick={() => handleSelect(result.symbol)}
                  className={`w-full px-4 py-2.5 text-left flex items-center justify-between transition-colors ${
                    idx === selectedIdx ? 'bg-primary/10 border-l-2 border-l-primary' : 'hover:dark:bg-muted/50 hover:bg-muted border-l-2 border-l-transparent'
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-bold text-primary">{result.symbol}</span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">{result.name}</p>
                  </div>
                  <div className="text-right flex-shrink-0 ml-4">
                    <span className="text-[10px] font-mono text-muted-foreground block">{result.type || 'Equity'}</span>
                    <span className="text-[10px] font-mono text-muted-foreground/60">{result.exchange}</span>
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
