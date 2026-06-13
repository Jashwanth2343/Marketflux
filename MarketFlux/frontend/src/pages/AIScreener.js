import React, { useState, useEffect, useRef, useCallback, memo } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ChevronDown } from 'lucide-react';
import { Search, Zap, TrendingUp, TrendingDown, Loader2, X, Filter, BarChart3 } from 'lucide-react';
import api from '@/lib/api';

function formatPrice(val) {
  if (!val && val !== 0) return '--';
  return Number(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function formatLarge(val) {
  if (!val) return '--';
  if (typeof val === 'string') return val;
  if (val >= 1e12) return `$${(val / 1e12).toFixed(2)}T`;
  if (val >= 1e9) return `$${(val / 1e9).toFixed(2)}B`;
  if (val >= 1e6) return `$${(val / 1e6).toFixed(2)}M`;
  return `$${val.toLocaleString()}`;
}

function FilterChips({ filters }) {
  const chips = [];
  if (filters.sector && filters.sector !== "All") chips.push({ label: filters.sector, type: 'sector' });
  if (filters.market_cap_range && filters.market_cap_range !== "Any") chips.push({ label: filters.market_cap_range, type: 'cap' });

  if (filters.filters_applied?.length) {
    filters.filters_applied.forEach(f => chips.push({ label: f, type: 'other' }));
  }

  if (!chips.length) return null;

  return (
    <div className="flex flex-wrap gap-1.5" data-testid="filter-chips">
      <Filter className="w-3.5 h-3.5 text-muted-foreground mt-0.5" />
      {chips.map((chip, i) => (
        <Badge
          key={i}
          variant="outline"
          className="rounded-none text-[10px] font-mono border-primary/40 text-primary"
        >
          {chip.label}
        </Badge>
      ))}
    </div>
  );
}

const TradingViewScreenerWidget = memo(() => {
  const container = useRef(null);

  useEffect(() => {
    // Only append if the container is empty (prevents StrictMode double-mount issues)
    const currentContainer = container.current;
    if (currentContainer && currentContainer.innerHTML === '') {
      const script = document.createElement('script');
      script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-screener.js';
      script.type = 'text/javascript';
      script.async = true;
      script.innerHTML = JSON.stringify({
        "width": "100%",
        "height": 800,
        "defaultColumn": "overview",
        "defaultScreen": "general",
        "market": "america",
        "showToolbar": true,
        "colorTheme": "dark",
        "locale": "en"
      });
      currentContainer.appendChild(script);
    }
  }, []);

  return (
    <div className="tradingview-widget-container border border-border" style={{ height: "800px", width: "100%" }}>
      <div className="tradingview-widget-container__widget" ref={container} style={{ height: "100%", width: "100%" }}></div>
    </div>
  );
});

export default function AIScreener({ embedded = false }) {
  const [useAIScreener, setUseAIScreener] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [cache, setCache] = useState({});

  const runScreen = useCallback(async (q) => {
    const screenQuery = (q ?? '').trim();
    if (!screenQuery) return;
    setQuery(screenQuery);

    if (cache[screenQuery]) {
      setResults(cache[screenQuery]);
      return;
    }

    setLoading(true);
    setError('');
    setResults(null);

    try {
      const res = await api.post('/ai/screen', { query: screenQuery });
      setResults(res.data);
      setCache(prev => ({ ...prev, [screenQuery]: res.data }));
    } catch (err) {
      if (err.response?.status === 429) {
        setError('AI usage limit reached. Please login for unlimited access.');
      } else {
        setError('Failed to process your query. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }, [cache]);

  const handleScreen = (e) => {
    e.preventDefault();
    runScreen(query);
  };

  // Accept a screen query handed off from the Intelligence command line
  // (stashed in sessionStorage just before this tab mounts, plus a live event).
  useEffect(() => {
    const consume = (q) => {
      const screenQuery = (q || '').trim();
      if (!screenQuery) return;
      setUseAIScreener(true);
      runScreen(screenQuery);
      try { sessionStorage.removeItem('mf_screener_query'); } catch { /* ignore */ }
    };
    let stashed = null;
    try { stashed = sessionStorage.getItem('mf_screener_query'); } catch { /* ignore */ }
    if (stashed) consume(stashed);
    const handler = (e) => consume(e.detail);
    window.addEventListener('mf:screener-query', handler);
    return () => window.removeEventListener('mf:screener-query', handler);
  }, [runScreen]);

  const suggestions = [
    'Show me large cap tech stocks with low P/E',
    'High dividend healthcare stocks',
    'Undervalued energy companies',
    'Low volatility consumer stocks',
    'Compare AAPL, MSFT, GOOGL, NVDA',
  ];

  const content = (
    <>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            {useAIScreener ? <Zap className="w-5 h-5 text-primary" /> : <BarChart3 className="w-5 h-5 text-secondary" />}
            <h1 className="text-xl md:text-2xl font-mono font-bold tracking-tight text-foreground">
              Market{' '}
              <span style={useAIScreener
                ? { color: '#E3B85F', textShadow: '0 0 10px rgba(227,184,95,0.4)' }
                : { color: 'hsl(var(--secondary))', textShadow: '0 0 10px rgba(146,152,166,0.4)' }}>
                Screener
              </span>
            </h1>
          </div>
          <p className="text-[11px] font-mono text-muted-foreground">
            {useAIScreener ? "Natural language → AI-generated filters → matched stocks" : "Full market screener powered by TradingView"}
          </p>
        </div>

        {/* Mode toggle */}
        <div
          className="flex rounded-lg overflow-hidden flex-shrink-0"
          style={{ border: '1px solid hsl(var(--border))', background: 'hsl(var(--muted) / 0.35)' }}
        >
          <button
            onClick={() => setUseAIScreener(false)}
            className="px-3 py-2 flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider transition-all"
            style={!useAIScreener ? {
              background: 'rgba(146,152,166,0.1)', color: 'hsl(var(--secondary))',
              borderRight: '1px solid hsl(var(--border))',
            } : {
              color: 'rgba(255,255,255,0.35)',
              borderRight: '1px solid hsl(var(--border))',
            }}
          >
            <BarChart3 className="w-3.5 h-3.5" /> Standard
          </button>
          <button
            onClick={() => setUseAIScreener(true)}
            className="px-3 py-2 flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider transition-all"
            style={useAIScreener ? {
              background: 'hsl(var(--primary) / 0.1)', color: '#E3B85F',
            } : {
              color: 'rgba(255,255,255,0.35)',
            }}
          >
            <Zap className="w-3.5 h-3.5" /> AI Mode
          </button>
        </div>
      </div>

      {!useAIScreener ? (
        <TradingViewScreenerWidget />
      ) : (
        <>
          {/* AI disclaimer */}
          <div
            className="flex gap-3 p-3 rounded-xl"
            style={{ background: 'hsl(var(--primary) / 0.06)', border: '1px solid rgba(227,184,95,0.2)' }}
          >
            <Zap className="w-4 h-4 shrink-0 mt-0.5 text-primary" />
            <p className="text-[11px] font-mono text-primary leading-relaxed">
              AI interprets your query into dynamic stock filters. Results may vary — always verify before trading.
            </p>
          </div>

          {/* Search box */}
          <div
            className="rounded-xl p-4 space-y-3"
            style={{ background: 'hsl(var(--muted) / 0.35)', border: '1px solid hsl(var(--border))' }}
          >
            <form data-testid="screener-form" onSubmit={handleScreen} className="space-y-3">
              <div className="relative">
                <Zap className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-primary" />
                <Input
                  data-testid="screener-input"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g. 'Large-cap tech with low P/E and strong earnings growth'"
                  className="pl-10 h-11 font-mono text-sm rounded-lg"
                  style={{
                    background: 'hsl(var(--muted) / 0.35)',
                    border: '1px solid hsl(var(--border))',
                  }}
                />
              </div>
              <div className="flex items-center gap-2">
                <Button
                  data-testid="screener-submit"
                  type="submit"
                  disabled={loading || !query.trim()}
                  size="sm"
                  className="h-9 px-5 text-[11px] font-mono uppercase tracking-wider rounded-lg"
                  style={{ background: 'hsl(var(--primary))', color: 'hsl(var(--primary-foreground))' }}
                >
                  {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Search className="w-3.5 h-3.5 mr-1.5" />}
                  Screen Stocks
                </Button>
                {results && (
                  <Button
                    data-testid="screener-clear"
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => { setResults(null); setQuery(''); }}
                    className="h-9 text-[11px] font-mono text-muted-foreground hover:text-foreground rounded-lg"
                  >
                    <X className="w-3 h-3 mr-1" /> Clear
                  </Button>
                )}
              </div>
            </form>

            {/* Suggestions */}
            {!results && (
              <div className="space-y-2 pt-1">
                <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">Try these:</p>
                <div className="flex flex-wrap gap-2">
                  {suggestions.map(s => (
                    <button
                      key={s}
                      data-testid={`suggestion-${s.slice(0, 20).replace(/\s/g, '-')}`}
                      onClick={() => setQuery(s)}
                      className="px-2.5 py-1.5 text-[10px] font-mono rounded-full transition-all"
                      style={{
                        background: 'hsl(var(--primary) / 0.06)',
                        border: '1px solid rgba(227,184,95,0.18)',
                        color: 'hsl(var(--primary) / 0.7)',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.background = 'hsl(var(--primary) / 0.12)';
                        e.currentTarget.style.color = '#E3B85F';
                        e.currentTarget.style.borderColor = 'hsl(var(--primary) / 0.35)';
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.background = 'hsl(var(--primary) / 0.06)';
                        e.currentTarget.style.color = 'hsl(var(--primary) / 0.7)';
                        e.currentTarget.style.borderColor = 'hsl(var(--primary) / 0.18)';
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Error */}
          {error && (
            <Card className="rounded-none border-destructive/50 bg-destructive/5">
              <CardContent className="p-4">
                <p className="text-xs font-mono text-destructive" data-testid="screener-error">{error}</p>
              </CardContent>
            </Card>
          )}

          {/* Loading */}
          {loading && (
            <div className="py-12 text-center">
              <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-3" />
              <p className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
                Converting query to filters & screening stocks<span className="cursor-blink">_</span>
              </p>
            </div>
          )}

          {/* Results */}
          {results && !loading && (
            <div className="space-y-4">

              {/* Transparency Card */}
              {results.interpreted_as && (
                <Collapsible className="border border-border bg-card/30 mt-4">
                  <CollapsibleTrigger className="flex w-full items-center justify-between p-3 font-mono text-xs uppercase tracking-wider text-muted-foreground hover:bg-muted/10">
                    <div className="flex items-center gap-2">
                      <Filter className="w-4 h-4 text-primary" />
                      How I interpreted your search
                    </div>
                    <ChevronDown className="w-4 h-4" />
                  </CollapsibleTrigger>
                  <CollapsibleContent className="p-3 border-t border-border space-y-3 bg-muted/5">
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline" className="rounded-none font-mono text-[10px] text-blue-400 border-blue-400/40">Sector: {results.interpreted_as.sector}</Badge>
                      <Badge variant="outline" className="rounded-none font-mono text-[10px] text-orange-400 border-orange-400/40">MCap: {results.interpreted_as.market_cap_range}</Badge>
                      {(results.interpreted_as.filters_applied || []).map((f, i) => (
                        <Badge key={i} variant="outline" className="rounded-none font-mono text-[10px] text-green-400 border-green-400/40">{f}</Badge>
                      ))}
                    </div>
                  </CollapsibleContent>
                </Collapsible>
              )}

              {/* Suggestion */}
              {results.suggestion && (
                <div className="bg-amber-500/10 border border-amber-500/30 p-3 mt-2">
                  <p className="text-xs font-mono text-amber-500">{results.suggestion}</p>
                </div>
              )}


              {/* Result count */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-primary" />
                  <span className="text-sm font-mono text-foreground" data-testid="results-count">
                    {results.result_count || results.total || results.stocks?.length || 0} stocks matched
                  </span>
                </div>
              </div>

              {/* AI Summary */}
              {results.summary && (
                <Card className="rounded-none border-primary/30 bg-primary/5">
                  <CardContent className="p-4 flex items-start gap-3">
                    <Zap className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-[10px] font-mono text-primary uppercase tracking-wider mb-1">AI Analysis</p>
                      <p className="text-sm text-foreground leading-relaxed" data-testid="ai-summary">{results.summary}</p>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Stock Results Table */}
              {results.stocks?.length > 0 && (
                <div
                  className="rounded-xl overflow-hidden"
                  style={{ border: '1px solid hsl(var(--border))', background: 'hsl(var(--muted) / 0.35)' }}
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm" data-testid="screener-results-table">
                      <thead>
                        <tr className="border-b" style={{ borderColor: 'hsl(var(--muted) / 0.5)', background: 'hsl(var(--muted) / 0.35)' }}>
                          <th className="text-left px-4 py-2.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Ticker</th>
                          <th className="text-left px-4 py-2.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hidden sm:table-cell">Company</th>
                          <th className="text-left px-4 py-2.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hidden lg:table-cell">Sector</th>
                          <th className="text-right px-4 py-2.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Price</th>
                          <th className="text-right px-4 py-2.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Change</th>
                          <th className="text-right px-4 py-2.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hidden md:table-cell">MCap</th>
                          <th className="text-right px-4 py-2.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hidden md:table-cell">P/E</th>
                          <th className="text-right px-4 py-2.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hidden lg:table-cell">Volume</th>
                          <th className="text-right px-4 py-2.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hidden lg:table-cell">Yield</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.stocks.map((stock) => {
                          const isPositive = stock.change_percent >= 0;
                          return (
                            <tr
                              key={stock.symbol}
                              className="border-b transition-colors"
                              style={{ borderColor: 'hsl(var(--muted) / 0.5)' }}
                              onMouseEnter={e => { e.currentTarget.style.background = 'hsl(var(--primary) / 0.04)'; }}
                              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                            >
                              <td className="px-4 py-2.5">
                                <Link
                                  to={`/stock/${stock.symbol}`}
                                  data-testid={`screener-result-${stock.symbol}`}
                                  className="flex items-center gap-2 group"
                                >
                                  <span className="font-mono font-bold text-foreground group-hover:text-primary transition-colors">
                                    {stock.symbol}
                                  </span>
                                </Link>
                              </td>
                              <td className="px-4 py-2.5 hidden sm:table-cell">
                                <span className="text-[10px] text-muted-foreground truncate max-w-[150px] inline-block" title={stock.name}>{stock.name || '--'}</span>
                              </td>
                              <td className="px-4 py-2.5 hidden lg:table-cell">
                                <span className="text-[10px] font-mono text-muted-foreground">{stock.sector || '--'}</span>
                              </td>
                              <td className="px-4 py-2.5 text-right">
                                <span className="font-data text-foreground">${formatPrice(stock.price)}</span>
                              </td>
                              <td className="px-4 py-2.5 text-right">
                                <span className={`font-data flex items-center justify-end gap-1 ${isPositive ? 'text-gain' : 'text-loss'}`}>
                                  {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                  {isPositive ? '+' : ''}{stock.change_percent?.toFixed(2)}%
                                </span>
                              </td>
                              <td className="px-4 py-2.5 text-right hidden md:table-cell">
                                <span className="font-data text-xs text-muted-foreground">{formatLarge(stock.market_cap)}</span>
                              </td>
                              <td className="px-4 py-2.5 text-right hidden md:table-cell">
                                <span className="font-data text-xs text-foreground">{stock.pe_ratio?.toFixed(1) || '--'}</span>
                              </td>
                              <td className="px-4 py-2.5 text-right hidden lg:table-cell">
                                <span className="font-data text-xs text-muted-foreground">{formatLarge(stock.volume)}</span>
                              </td>
                              <td className="px-4 py-2.5 text-right hidden lg:table-cell">
                                <span className="font-data text-xs text-muted-foreground">{stock.dividend_yield || '--'}</span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {results.stocks?.length === 0 && (
                <div className="py-12 flex flex-col items-center gap-3 text-center">
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center"
                    style={{ background: 'hsl(var(--primary) / 0.07)', border: '1px solid rgba(227,184,95,0.15)' }}
                  >
                    <Search className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-mono font-semibold text-foreground mb-1" data-testid="no-results">No stocks matched</p>
                    <p className="text-xs font-mono text-muted-foreground">Try broadening your criteria or rephrasing the query</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </>
  );

  if (embedded) return content;

  return (
    <div className="p-4 lg:p-6 space-y-4 grid-bg min-h-screen" data-testid="ai-screener-page">
      {content}
    </div>
  );
}
