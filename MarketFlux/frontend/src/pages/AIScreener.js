import React, { useState, useEffect, useRef, memo } from 'react';
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
          className="rounded-none text-[10px] font-mono border-[#FFB000]/40 text-[#FFB000]"
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

export default function AIScreener() {
  const [useAIScreener, setUseAIScreener] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [cache, setCache] = useState({});

  const handleScreen = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    if (cache[query]) {
      setResults(cache[query]);
      return;
    }

    setLoading(true);
    setError('');
    setResults(null);

    try {
      const res = await api.post('/ai/screen', { query });
      setResults(res.data);
      setCache(prev => ({ ...prev, [query]: res.data }));
    } catch (err) {
      if (err.response?.status === 429) {
        setError('AI usage limit reached. Please login for unlimited access.');
      } else {
        setError('Failed to process your query. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const suggestions = [
    'Show me large cap tech stocks with low P/E',
    'High dividend healthcare stocks',
    'Undervalued energy companies',
    'Low volatility consumer stocks',
    'Compare AAPL, MSFT, GOOGL, NVDA',
  ];

  return (
    <div className="p-4 lg:p-6 space-y-4 grid-bg min-h-screen" data-testid="ai-screener-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-3xl font-bold tracking-tighter uppercase text-foreground">
            Market <span className={useAIScreener ? "text-[#FFB000] glow-amber" : "text-[#00F3FF] glow-blue"}>Screener</span>
          </h1>
          <p className="text-xs font-mono text-muted-foreground mt-1">
            {useAIScreener ? "Describe what you're looking for — AI converts it to filters" : "Track all markets and screen for opportunities"}
          </p>
        </div>

        {/* Toggle Button */}
        <button
          onClick={() => setUseAIScreener(!useAIScreener)}
          className={`px-4 py-2 flex items-center gap-2 text-xs font-mono uppercase tracking-wider border transition-colors ${useAIScreener
            ? "bg-[#FFB000]/10 border-[#FFB000] text-[#FFB000]"
            : "bg-card border-border text-muted-foreground hover:bg-muted"
            }`}
        >
          {useAIScreener ? <Zap className="w-4 h-4" /> : <BarChart3 className="w-4 h-4" />}
          {useAIScreener ? "Use Standard Screener" : "Use AI Screener"}
        </button>
      </div>

      {!useAIScreener ? (
        <TradingViewScreenerWidget />
      ) : (
        <>
          <div className="bg-[#FFB000]/10 border border-[#FFB000]/40 p-3 flex gap-3 text-[#FFB000]">
            <Zap className="w-4 h-4 shrink-0 mt-0.5" />
            <p className="text-[10px] font-mono leading-relaxed">
              <strong>AI Screener Mode Component:</strong> Natural language based screener - results might take time. Since AI generates the exact filters dynamically, results may vary or occasionally be inaccurate.
            </p>
          </div>

          {/* Search */}
          <Card className="rounded-none border-border dark:bg-card/50 bg-card">
            <CardContent className="p-4">
              <form data-testid="screener-form" onSubmit={handleScreen} className="space-y-3">
                <div className="relative">
                  <Zap className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#FFB000]" />
                  <Input
                    data-testid="screener-input"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="e.g. 'Show me large cap tech stocks with a low P/E ratio'"
                    className="pl-12 pr-4 py-6 rounded-none bg-background border-border font-mono text-sm text-foreground placeholder:text-muted-foreground/50"
                  />
                </div>
                <div className="flex items-center gap-3">
                  <Button
                    data-testid="screener-submit"
                    type="submit"
                    disabled={loading || !query.trim()}
                    className="rounded-none bg-[#FFB000] text-black font-mono text-xs uppercase tracking-wider hover:bg-[#FFB000]/80"
                  >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Search className="w-4 h-4 mr-2" />}
                    Screen Stocks
                  </Button>
                  {results && (
                    <Button
                      data-testid="screener-clear"
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => { setResults(null); setQuery(''); }}
                      className="rounded-none text-xs font-mono text-muted-foreground hover:text-foreground"
                    >
                      <X className="w-3 h-3 mr-1" /> Clear
                    </Button>
                  )}
                </div>
              </form>

              {/* Suggestions */}
              {!results && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {suggestions.map(s => (
                    <button
                      key={s}
                      data-testid={`suggestion-${s.slice(0, 20).replace(/\s/g, '-')}`}
                      onClick={() => setQuery(s)}
                      className="px-2 py-1 text-[10px] font-mono uppercase border border-border text-muted-foreground hover:border-[#FFB000] hover:text-[#FFB000] transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

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
              <Loader2 className="w-8 h-8 animate-spin text-[#FFB000] mx-auto mb-3" />
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
                <Card className="rounded-none border-[#FFB000]/30 bg-[#FFB000]/5">
                  <CardContent className="p-4 flex items-start gap-3">
                    <Zap className="w-4 h-4 text-[#FFB000] flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-[10px] font-mono text-[#FFB000] uppercase tracking-wider mb-1">AI Analysis</p>
                      <p className="text-sm text-foreground leading-relaxed" data-testid="ai-summary">{results.summary}</p>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Stock Results Table */}
              {results.stocks?.length > 0 && (
                <Card className="rounded-none border-border dark:bg-card/50 bg-card overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm" data-testid="screener-results-table">
                      <thead>
                        <tr className="border-b border-border dark:bg-muted/30 bg-muted">
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
                              className="border-b dark:border-border/50 border-border hover:dark:bg-muted/20 hover:bg-muted transition-colors"
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
                                <span className={`font-data flex items-center justify-end gap-1 ${isPositive ? 'dark:text-[#00FF41] text-[#059669]' : 'text-[#FF3333]'}`}>
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
                </Card>
              )}

              {results.stocks?.length === 0 && (
                <div className="py-8 text-center">
                  <p className="text-sm font-mono text-muted-foreground" data-testid="no-results">No stocks matched your criteria. Try broadening your filters.</p>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
