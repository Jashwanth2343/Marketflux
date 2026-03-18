import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import DOMPurify from 'dompurify';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { TrendingUp, TrendingDown, ArrowLeft, Zap, BarChart3, DollarSign, Activity, Clock, Star, Target, Users, UserCheck, RefreshCw, LineChart, Loader2, Info, Maximize2 } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ComposedChart, Bar, Cell, ReferenceLine, CartesianGrid } from 'recharts';
import { useTheme } from '@/contexts/ThemeContext';
import NewsCard from '@/components/NewsCard';
import api from '@/lib/api';

function fmt(val, opts = {}) {
  if (val === null || val === undefined) return '--';
  const { prefix = '', suffix = '', decimals = 2, compact = false } = opts;
  const num = Number(val);
  if (isNaN(num)) return '--';
  if (compact) {
    if (Math.abs(num) >= 1e12) return `${prefix}${(num / 1e12).toFixed(2)}T${suffix}`;
    if (Math.abs(num) >= 1e9) return `${prefix}${(num / 1e9).toFixed(2)}B${suffix}`;
    if (Math.abs(num) >= 1e6) return `${prefix}${(num / 1e6).toFixed(2)}M${suffix}`;
  }
  return `${prefix}${num.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}${suffix}`;
}

function pctFmt(val) {
  if (val === null || val === undefined) return '--';
  return `${(Number(val) * 100).toFixed(2)}%`;
}

function renderMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^### (.*$)/gm, '<h3>$1</h3>')
    .replace(/^## (.*$)/gm, '<h2>$1</h2>')
    .replace(/^\- (.*$)/gm, '<li>$1</li>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>');
}

function StatRow({ label, value }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-border/30">
      <span className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">{label}</span>
      <span className="font-data text-xs text-foreground">{value}</span>
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const price = payload[0].value;
    const volume = data.volume;
    const change = data.change_from_prev;

    return (
      <div className="bg-[#0A0A0A] border border-border p-2 shadow-2xl rounded-none font-mono text-[10px] min-w-[140px] z-50">
        <div className="text-muted-foreground mb-1 border-b border-border/50 pb-1 flex justify-between">
          <span>{label}</span>
          <Clock className="w-3 h-3 opacity-50" />
        </div>
        <div className="space-y-1 mt-1.5">
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">PRICE</span>
            <span className="text-foreground font-bold">${price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
          </div>
          {change !== undefined && (
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">CHANGE</span>
              <span className={change >= 0 ? 'text-[#3FB950]' : 'text-[#F85149]'}>
                {change >= 0 ? '+' : ''}{change.toFixed(2)}%
              </span>
            </div>
          )}
          {volume && (
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">VOLUME</span>
              <span className="text-foreground">{fmt(volume, { compact: true })}</span>
            </div>
          )}
        </div>
      </div>
    );
  }
  return null;
};

export default function StockDetail() {
  const { ticker } = useParams();
  const location = useLocation();
  const { isDark } = useTheme();

  // PROBLEM 3: Show basic info instantly from navigation state
  const [stock, setStock] = useState(location.state?.initialData || null);
  const [chart, setChart] = useState([]);
  const [news, setNews] = useState([]);
  const [period, setPeriod] = useState('1mo');
  const [loading, setLoading] = useState(!location.state?.initialData);
  const [isWatched, setIsWatched] = useState(false);

  // PROBLEM 2: Chart caching
  const chartCache = useRef({});
  const [chartLoading, setChartLoading] = useState(false);

  // TradingView advanced chart
  const [showAdvancedChart, setShowAdvancedChart] = useState(false);
  const tvContainerRef = useRef(null);
  const tvWidgetLoaded = useRef(false);

  // AI Digest
  const [digest, setDigest] = useState(null);
  const [digestLoading, setDigestLoading] = useState(false);

  const getInterval = (p) => {
    switch (p) {
      case '1d': return '5m';
      case '5d': return '15m';
      case '1mo': return '1d';
      case '6mo': return '1d';
      case '1y': return '1wk';
      case '5y': return '1mo';
      default: return '1d';
    }
  };

  const loadChartForPeriod = useCallback(async (p, isInitial = false) => {
    const cacheKey = `${ticker}_${p}`;
    if (chartCache.current[cacheKey]) {
      setChart(chartCache.current[cacheKey]);
      return chartCache.current[cacheKey];
    }

    if (!isInitial) setChartLoading(true);
    try {
      const res = await api.get(`/market/chart/${ticker}?period=${p}&interval=${getInterval(p)}`);
      const data = res.data.data || [];
      chartCache.current[cacheKey] = data;
      setChart(data);
      return data;
    } catch (e) {
      console.error('Chart fetch error:', e);
      return [];
    } finally {
      if (!isInitial) setChartLoading(false);
    }
  }, [ticker]);

  useEffect(() => {
    const fetchData = async () => {
      // If we don't have stock data yet, show global loading
      if (!stock) setLoading(true);

      try {
        // PROBLEM 1: Parallelize all initial data calls
        const [stockRes, newsRes, watchRes, initialChart] = await Promise.all([
          api.get(`/market/stock/${ticker}/rich`),
          api.get(`/news/ticker/${ticker}`),
          api.get('/watchlist'),
          loadChartForPeriod(period, true)
        ]);

        setStock(stockRes.data);
        setNews(newsRes.data.articles || []);
        setIsWatched((watchRes.data.tickers || []).includes(ticker.toUpperCase()));
        setChart(initialChart);
      } catch (e) {
        console.error('Data fetch error:', e);
      } finally {
        setLoading(false);
      }
    };
    if (ticker) fetchData();
  }, [ticker]); // Only run on ticker change

  // Handle period changes separately to use cache
  useEffect(() => {
    if (ticker && !loading) {
      loadChartForPeriod(period);
    }
  }, [period, loadChartForPeriod]);

  // PROBLEM 2: Pre-warm common chart periods in background
  useEffect(() => {
    if (ticker) {
      const preWarm = async () => {
        const commonPeriods = ['1d', '1y']; // 1mo is loaded by default
        for (const p of commonPeriods) {
          if (!chartCache.current[`${ticker}_${p}`]) {
            // Fetch silently in background
            api.get(`/market/chart/${ticker}?period=${p}&interval=${getInterval(p)}`)
              .then(res => {
                chartCache.current[`${ticker}_${p}`] = res.data.data || [];
              }).catch(() => {});
          }
        }
      };
      // Delay slightly to not compete with initial load
      const timer = setTimeout(preWarm, 2000);
      return () => clearTimeout(timer);
    }
  }, [ticker]);

  // Fetch AI Digest
  const fetchDigest = useCallback(async (refresh = false) => {
    setDigestLoading(true);
    try {
      const res = await api.get(`/stock-digest/${ticker}${refresh ? '?refresh=true' : ''}`);
      setDigest(res.data);
    } catch (err) {
      console.error('Digest fetch error:', err);
    } finally {
      setDigestLoading(false);
    }
  }, [ticker]);

  useEffect(() => {
    if (ticker) fetchDigest();
  }, [ticker, fetchDigest]);

  // TradingView widget
  useEffect(() => {
    if (!showAdvancedChart || !tvContainerRef.current) return;
    // Clear container
    tvContainerRef.current.innerHTML = '';
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      "autosize": true,
      "symbol": ticker.toUpperCase(),
      "interval": "D",
      "timezone": "Etc/UTC",
      "theme": isDark ? "dark" : "light",
      "style": "1",
      "locale": "en",
      "allow_symbol_change": true,
      "calendar": false,
      "support_host": "https://www.tradingview.com",
    });
    tvContainerRef.current.appendChild(script);
    tvWidgetLoaded.current = true;
  }, [showAdvancedChart, isDark, ticker]);

  const toggleWatchlist = async () => {
    try {
      if (isWatched) {
        await api.delete(`/watchlist/${ticker}`);
        setIsWatched(false);
      } else {
        await api.post('/watchlist', { ticker: ticker.toUpperCase() });
        setIsWatched(true);
      }
    } catch (err) {
      console.error('Watchlist toggle error:', err);
    }
  };

  const periods = [
    { label: '1D', value: '1d' },
    { label: '5D', value: '5d' },
    { label: '1M', value: '1mo' },
    { label: '6M', value: '6mo' },
    { label: '1Y', value: '1y' },
    { label: '5Y', value: '5y' },
  ];

  const isPositive = stock?.change_percent >= 0;
  const asOf = stock?.last_updated ? new Date(stock.last_updated).toLocaleString() : '';

  if (loading && !stock) {
    return (
      <div className="p-6 grid-bg min-h-screen flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!loading && !stock) {
    return (
      <div className="p-6 grid-bg min-h-screen flex flex-col items-center justify-center text-center">
        <Activity className="w-12 h-12 text-muted-foreground/50 mb-4" />
        <h2 className="text-xl font-bold text-foreground mb-2">Stock Not Found</h2>
        <p className="text-muted-foreground text-sm max-w-md mb-6">
          We couldn't find any market data for "{ticker}". Please check the ticker symbol and try again.
        </p>
        <Link to="/">
          <Button variant="default" className="gap-2">
            <ArrowLeft className="w-4 h-4" /> Return to Dashboard
          </Button>
        </Link>
      </div>
    );
  }

  // Digest timestamp
  const digestAge = digest?.timestamp
    ? Math.round((Date.now() - new Date(digest.timestamp).getTime()) / 60000)
    : null;

  return (
    <div className="p-4 lg:p-6 space-y-4 grid-bg min-h-screen" data-testid="stock-detail-page">
      {/* Back */}
      <Link to="/" data-testid="back-to-dashboard">
        <Button variant="ghost" size="sm" className="rounded-none font-mono text-xs">
          <ArrowLeft className="w-4 h-4 mr-1" /> Back
        </Button>
      </Link>

      {/* Header */}
      {stock && (
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-2">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-2xl md:text-4xl font-bold tracking-tighter uppercase text-foreground flex items-center gap-3">
                {stock.symbol}
                <button onClick={toggleWatchlist} className="focus:outline-none transition-transform hover:scale-110">
                  <Star className={`w-6 h-6 ${isWatched ? 'fill-[#00FF41] dark:text-[#00FF41] text-[#059669] drop-shadow-[0_0_8px_rgba(0,255,65,0.6)]' : 'text-muted-foreground/50 hover:text-foreground'}`} />
                </button>
              </h1>
              {stock.exchange && <Badge variant="outline" className="rounded-none text-[8px] font-mono border-border text-muted-foreground ml-2">{stock.exchange}</Badge>}
            </div>
            <p className="text-sm text-muted-foreground">{stock.name}</p>
            <div className="flex items-center gap-2 mt-1">
              {stock.sector && <Badge variant="outline" className="rounded-none text-[8px] font-mono border-secondary/30 text-secondary">{stock.sector}</Badge>}
              {stock.industry && <Badge variant="outline" className="rounded-none text-[8px] font-mono border-border text-muted-foreground">{stock.industry}</Badge>}
            </div>
          </div>
          <div className="text-right">
            <p className="font-data text-3xl text-foreground">${fmt(stock.price)}</p>
            <div className={`flex items-center justify-end gap-1 font-data text-sm ${isPositive ? 'dark:text-[#00FF41] text-[#059669]' : 'text-[#FF3333]'}`}>
              {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
              {isPositive ? '+' : ''}{fmt(stock.change)} ({isPositive ? '+' : ''}{stock.change_percent?.toFixed(2)}%)
            </div>
            <div className="flex items-center justify-end gap-1 mt-1">
              <Clock className="w-3 h-3 text-muted-foreground/50" />
              <span className="text-[9px] font-mono text-muted-foreground/50">As of {asOf}</span>
            </div>
          </div>
        </div>
      )}

      {/* Data disclaimer */}
      <p className="text-[9px] font-mono text-muted-foreground/40">Market data may be delayed up to 15 minutes. Not investment advice.</p>

      {/* Chart */}
      <Card className="rounded-none border-border dark:bg-card/50 bg-card">
        <CardHeader className="pb-2 pt-3 px-4 flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-mono uppercase tracking-wider">Price Chart</CardTitle>
          <div className="flex items-center gap-2">
            {!showAdvancedChart && (
              <div className="flex gap-1">
                {periods.map(p => (
                  <button
                    key={p.value}
                    data-testid={`period-${p.value}`}
                    onClick={() => setPeriod(p.value)}
                    className={`px-2 py-1 text-[10px] font-mono uppercase border transition-colors ${period === p.value ? 'border-primary text-primary bg-primary/10' : 'border-border text-muted-foreground hover:text-foreground'
                      }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            )}
            <button
              data-testid="toggle-advanced-chart"
              onClick={() => setShowAdvancedChart(!showAdvancedChart)}
              className={`px-3 py-1 text-[10px] font-mono uppercase border flex items-center gap-1.5 transition-colors ${showAdvancedChart ? 'border-primary text-primary bg-primary/10' : 'border-border text-muted-foreground hover:text-foreground hover:border-primary'}`}
            >
              <LineChart className="w-3.5 h-3.5" />
              {showAdvancedChart ? 'Simple Chart' : 'Advanced Chart'}
            </button>
          </div>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          {showAdvancedChart ? (
            <div className="tradingview-widget-container" style={{ height: '500px', width: '100%' }}>
              <div className="tradingview-widget-container__widget" ref={tvContainerRef} style={{ height: '100%', width: '100%' }} />
            </div>
          ) : (
            <>
            <>
              <div className="h-[350px] relative mt-2 group">
                {chartLoading && (
                  <div className="absolute inset-0 z-10 bg-background/50 backdrop-blur-[1px] flex items-center justify-center">
                    <Skeleton className="w-full h-full opacity-50" />
                  </div>
                )}
                
                {chart.length > 0 && (
                  <div className="absolute top-2 right-4 z-10">
                    {(() => {
                      const first = chart[0]?.close;
                      const last = chart[chart.length - 1]?.close;
                      if (!first || !last) return null;
                      const diff = last - first;
                      const pct = (diff / first) * 100;
                      const isUp = pct >= 0;
                      return (
                        <div className={`px-2 py-1 bg-background/80 backdrop-blur-md border rounded-md font-mono text-[10px] flex items-center gap-1.5 shadow-sm ${isUp ? 'border-[#3FB950]/30 text-[#3FB950]' : 'border-[#F85149]/30 text-[#F85149]'}`}>
                          <div className={`w-1.5 h-1.5 rounded-full ${isUp ? 'bg-[#3FB950]' : 'bg-[#F85149]'} animate-pulse`} />
                          <span className="font-bold">{isUp ? '+' : ''}{pct.toFixed(2)}%</span>
                          <span className="opacity-70 uppercase tracking-tighter">Past {period === '1mo' ? 'Month' : period === '1d' ? 'Day' : period === '1y' ? 'Year' : period}</span>
                        </div>
                      );
                    })()}
                  </div>
                )}

                {chart.length === 0 && !chartLoading ? (
                  <div className="w-full h-full flex items-center justify-center font-mono text-sm text-muted-foreground border border-dashed dark:border-border/50 border-border">
                    Chart data unavailable
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chart} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={isPositive ? '#3FB950' : '#F85149'} stopOpacity={0.3} />
                          <stop offset="95%" stopColor={isPositive ? '#3FB950' : '#F85149'} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)"} />
                      <XAxis 
                        dataKey="date" 
                        tick={{ fontSize: 9, fontFamily: 'JetBrains Mono', fill: '#A1A1AA' }} 
                        stroke="transparent" 
                        tickFormatter={(v) => {
                          if (period === '1d') return v?.split(' ')[1]?.slice(0, 5);
                          return v?.split(' ')[0]?.slice(5);
                        }} 
                      />
                      <YAxis 
                        yAxisId="price"
                        orientation="right"
                        domain={['auto', 'auto']} 
                        tick={{ fontSize: 9, fontFamily: 'JetBrains Mono', fill: '#A1A1AA' }} 
                        stroke="transparent" 
                        tickFormatter={(v) => `$${v}`} 
                      />
                      <YAxis 
                        yAxisId="volume"
                        orientation="left"
                        hide={true}
                        domain={[0, (dataMax) => dataMax * 5]}
                      />
                      
                      <Tooltip content={<CustomTooltip />} cursor={{ stroke: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)', strokeWidth: 1, strokeDasharray: '3 3' }} />
                      
                      {/* 52W Reference Lines for 1Y and 5Y */}
                      {(period === '1y' || period === '5y') && stock?.fifty_two_week_high && (
                        <ReferenceLine 
                          y={stock.fifty_two_week_high} 
                          yAxisId="price" 
                          stroke="#64748b" 
                          strokeDasharray="3 3" 
                          label={{ position: 'left', value: '52W HIGH', fill: '#64748b', fontSize: 8, fontFamily: 'JetBrains Mono' }} 
                        />
                      )}
                      {(period === '1y' || period === '5y') && stock?.fifty_two_week_low && (
                        <ReferenceLine 
                          y={stock.fifty_two_week_low} 
                          yAxisId="price" 
                          stroke="#64748b" 
                          strokeDasharray="3 3" 
                          label={{ position: 'left', value: '52W LOW', fill: '#64748b', fontSize: 8, fontFamily: 'JetBrains Mono' }} 
                        />
                      )}

                      <Area 
                        yAxisId="price"
                        type="monotone" 
                        dataKey="close" 
                        stroke={isPositive ? '#3FB950' : '#F85149'} 
                        fill="url(#chartGradient)" 
                        strokeWidth={2} 
                        dot={false} 
                        isAnimationActive={true}
                        animationDuration={600}
                      />
                      
                      <Bar 
                        yAxisId="volume"
                        dataKey="volume" 
                        isAnimationActive={true}
                        animationDuration={800}
                      >
                        {chart.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={isPositive ? '#3FB950' : '#F85149'} fillOpacity={0.15} />
                        ))}
                      </Bar>
                    </ComposedChart>
                  </ResponsiveContainer>
                )}
              </div>
              {chart.length > 0 && (
                <div className="flex flex-wrap gap-x-6 gap-y-2 mt-4 text-[10px] font-mono text-muted-foreground border-t border-border/30 pt-4">
                  <div className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/30"/> Open: <span className="text-foreground tracking-tighter">${fmt(stock?.open)}</span></div>
                  <div className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-[#3FB950]/40"/> High: <span className="text-foreground tracking-tighter">${fmt(stock?.day_high)}</span></div>
                  <div className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-[#F85149]/40"/> Low: <span className="text-foreground tracking-tighter">${fmt(stock?.day_low)}</span></div>
                  <div className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/30"/> Prev Close: <span className="text-foreground tracking-tighter">${fmt(stock?.previous_close)}</span></div>
                </div>
              )}
            </>
            </>
          )}
        </CardContent>
      </Card>

      {/* Flux AI Digest - Moved to Top */}
      <Card className="rounded-xl border border-primary/40 bg-background/60 backdrop-blur-xl shadow-[0_0_30px_rgba(0,255,65,0.15)] mb-6 relative overflow-hidden" data-testid="ai-digest-section">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent opacity-50 pointer-events-none" />
        <CardHeader className="pb-2 pt-4 px-5 flex flex-row items-center justify-between relative z-10 border-b border-border/30">
          <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" /> Flux AI Digest
            <span className="w-2 h-2 rounded-full bg-primary pulse-live" />
          </CardTitle>
          <div className="flex items-center gap-3">
            {digestAge != null && (
              <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">
                {digestAge < 1 ? 'Just refreshed' : `${digestAge}m ago`}
              </span>
            )}
            <Button
              data-testid="refresh-digest"
              variant="default"
              size="sm"
              onClick={() => fetchDigest(true)}
              disabled={digestLoading}
              className="rounded-md text-xs font-mono bg-primary/10 text-primary hover:bg-primary/20 hover:text-primary shadow-none border border-primary/20 p-2 h-auto transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${digestLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="px-5 pb-5 relative z-10 pt-4">
          {digestLoading && !digest ? (
            <div className="py-8 flex flex-col items-center gap-3">
              <Loader2 className="w-5 h-5 animate-spin text-primary" />
              <span className="font-mono text-xs text-muted-foreground uppercase tracking-widest">Generating Analyst Digest<span className="cursor-blink">_</span></span>
            </div>
          ) : digest?.digest ? (
            <div className="bg-muted/10 rounded-lg p-1">
              <div className="markdown-content text-[13.5px] leading-relaxed text-foreground/90 font-medium" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(renderMarkdown(digest.digest)) }} />
            </div>
          ) : (
            <p className="text-xs font-mono text-muted-foreground py-6 text-center uppercase tracking-widest">Digest unavailable. Click refresh to try again.</p>
          )}
        </CardContent>
      </Card>

      {/* Stats + Fundamentals Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Key Stats */}
        <Card className="rounded-none border-border dark:bg-card/50 bg-card corner-brackets">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-primary" /> Key Stats
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            {stock && (
              <div className="space-y-0">
                <StatRow label="Market Cap" value={fmt(stock.market_cap, { prefix: '$', compact: true })} />
                <StatRow label="P/E (TTM)" value={fmt(stock.pe_ratio)} />
                <StatRow label="Forward P/E" value={fmt(stock.forward_pe)} />
                <StatRow label="EPS (TTM)" value={fmt(stock.eps, { prefix: '$' })} />
                <StatRow label="Div Yield" value={stock.dividend_yield != null ? `${Number(stock.dividend_yield).toFixed(2)}%` : '--'} />
                <StatRow label="Payout Ratio" value={stock.payout_ratio ? pctFmt(stock.payout_ratio) : '--'} />
                <StatRow label="Beta" value={fmt(stock.beta)} />
                <StatRow label="52W High" value={fmt(stock.fifty_two_week_high, { prefix: '$' })} />
                <StatRow label="52W Low" value={fmt(stock.fifty_two_week_low, { prefix: '$' })} />
                <StatRow label="Volume" value={stock.volume?.toLocaleString() || '--'} />
                <StatRow label="Avg Volume" value={stock.avg_volume?.toLocaleString() || '--'} />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Fundamentals */}
        <Card className="rounded-none border-border dark:bg-card/50 bg-card corner-brackets">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4 text-secondary" /> Fundamentals
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            {stock && (
              <div className="space-y-0">
                <StatRow label="Revenue (TTM)" value={fmt(stock.revenue_ttm, { prefix: '$', compact: true })} />
                <StatRow label="Net Income" value={fmt(stock.net_income, { prefix: '$', compact: true })} />
                <StatRow label="Profit Margin" value={stock.profit_margin != null ? pctFmt(stock.profit_margin) : '--'} />
                <StatRow label="Operating Margin" value={stock.operating_margins != null ? pctFmt(stock.operating_margins) : '--'} />
                <StatRow label="Gross Margin" value={stock.gross_margins != null ? pctFmt(stock.gross_margins) : '--'} />
                <StatRow label="ROE" value={stock.roe != null ? pctFmt(stock.roe) : '--'} />
                <StatRow label="ROA" value={stock.roa != null ? pctFmt(stock.roa) : '--'} />
                <StatRow label="Debt/Equity" value={fmt(stock.debt_to_equity)} />
                <StatRow label="Current Ratio" value={fmt(stock.current_ratio)} />
                <StatRow label="Book Value" value={fmt(stock.book_value, { prefix: '$' })} />
                <StatRow label="Free Cash Flow" value={fmt(stock.free_cashflow, { prefix: '$', compact: true })} />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Dividends & Growth */}
        <Card className="rounded-none border-border dark:bg-card/50 bg-card corner-brackets">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-[#FFB000]" /> Dividends & Growth
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            {stock && (
              <div className="space-y-0">
                <StatRow label="Dividend Yield" value={stock.dividend_yield != null ? `${Number(stock.dividend_yield).toFixed(2)}%` : '--'} />
                <StatRow label="Last Dividend" value={stock.last_dividend_value ? fmt(stock.last_dividend_value, { prefix: '$' }) : '--'} />
                <StatRow label="Payout Ratio" value={stock.payout_ratio ? pctFmt(stock.payout_ratio) : '--'} />
                <StatRow label="5Y Avg Yield" value={stock.five_year_avg_dividend_yield != null ? `${Number(stock.five_year_avg_dividend_yield).toFixed(2)}%` : '--'} />
                <StatRow label="Earnings Growth" value={stock.earnings_growth ? pctFmt(stock.earnings_growth) : '--'} />
                <StatRow label="Revenue Growth" value={stock.revenue_growth ? pctFmt(stock.revenue_growth) : '--'} />
                {stock.recent_moves?.length > 0 && (
                  <>
                    <div className="pt-3 pb-1">
                      <span className="text-[10px] font-mono text-primary uppercase tracking-wider">Significant Moves (90d)</span>
                    </div>
                    {stock.recent_moves.slice(-5).map((m, i) => (
                      <div key={i} className="flex justify-between py-1 border-b border-border/30 text-[10px]">
                        <span className="font-mono text-muted-foreground">{m.date}</span>
                        <span className={`font-data ${m.change_pct > 0 ? 'dark:text-[#00FF41] text-[#059669]' : 'text-[#FF3333]'}`}>
                          {m.change_pct > 0 ? '+' : ''}{m.change_pct}%
                        </span>
                      </div>
                    ))}
                    <StatRow label="Max Drawdown" value={`${stock.max_drawdown_pct || 0}%`} />
                  </>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Analyst Price Targets */}
      {stock && stock.target_mean_price && (
        <Card className="rounded-none border-border dark:bg-card/50 bg-card corner-brackets" data-testid="analyst-targets">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
              <Target className="w-4 h-4 text-[#00F3FF]" /> Analyst Price Targets
              <button
                title="Price targets are forecasts by Wall Street analysts for where a stock's price may trade in the next 12 months. The bar shows the range from lowest to highest target. The mean (average) target represents the consensus view. The analyst score ranges from 1 (Strong Buy) to 5 (Strong Sell)."
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <Info className="w-3.5 h-3.5" />
              </button>
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6 mt-4 md:mt-6 mb-4">
              {/* Visual bar */}
              <div className="flex-1 w-full relative mt-8 mb-12 sm:mb-8">
                <div className="relative h-2 w-full dark:bg-muted/50 bg-muted rounded-full">
                  {/* Range bar */}
                  {(() => {
                    const low = stock.target_low_price || 0;
                    const high = stock.target_high_price || 0;
                    const mean = stock.target_mean_price || 0;
                    const price = stock.price || 0;
                    const min = Math.min(low, price) * 0.95;
                    const max = Math.max(high, price) * 1.05;
                    const range = max - min || 1;
                    const lowPct = ((low - min) / range) * 100;
                    const highPct = ((high - min) / range) * 100;
                    const meanPct = ((mean - min) / range) * 100;
                    const pricePct = ((price - min) / range) * 100;
                    return (
                      <>
                        <div className="absolute top-0 h-full rounded-full border border-[rgba(0,255,136,0.3)] transition-all duration-500" 
                             style={{ left: `${lowPct}%`, width: `${highPct - lowPct}%`, background: 'linear-gradient(to right, rgba(0,255,136,0.1), rgba(0,255,136,0.4))' }} />

                        {/* Low Target Label */}
                        <div className="absolute top-1/2 -mt-1 w-2 h-2 rounded-full bg-muted-foreground/40 z-10" style={{ left: `${lowPct}%`, transform: 'translateX(-50%)' }} />
                        <div className="absolute" style={{ left: `${lowPct}%`, top: '16px', transform: 'translateX(-50%)' }}>
                          <div className="flex flex-col items-center">
                            <span className="text-[9px] font-mono text-muted-foreground whitespace-nowrap">Low Target</span>
                            <span className="text-[10px] font-mono text-foreground font-bold">${low}</span>
                          </div>
                        </div>

                        {/* High Target Label */}
                        <div className="absolute top-1/2 -mt-1 w-2 h-2 rounded-full bg-muted-foreground/40 z-10" style={{ left: `${highPct}%`, transform: 'translateX(-50%)' }} />
                        <div className="absolute" style={{ left: `${highPct}%`, top: '16px', transform: 'translateX(-50%)' }}>
                          <div className="flex flex-col items-center">
                            <span className="text-[9px] font-mono text-muted-foreground whitespace-nowrap">High Target</span>
                            <span className="text-[10px] font-mono text-foreground font-bold">${high}</span>
                          </div>
                        </div>

                        {/* Analyst Mean Marker */}
                        <div className="absolute top-1/2 -mt-1.5 w-3 h-3 rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.7)] z-20" title={`Mean: $${mean}`} style={{ left: `${meanPct}%`, transform: 'translateX(-50%)' }} />
                        <div className="absolute" style={{ left: `${meanPct}%`, top: '-24px', transform: 'translateX(-50%)' }}>
                          <div className="text-[10px] font-mono text-white whitespace-nowrap font-bold">Mean: ${mean}</div>
                        </div>

                        {/* Current Price Marker */}
                        <div className="absolute top-1/2 -mt-[5px] w-2.5 h-2.5 rounded-full bg-[#FFB000] shadow-[0_0_8px_rgba(255,176,0,0.6)] z-30 ring-2 ring-background" title={`Current: $${price}`} style={{ left: `${pricePct}%`, transform: 'translateX(-50%)' }} />
                        <div className="absolute" style={{ left: `${pricePct}%`, bottom: '-46px', transform: 'translateX(-50%)' }}>
                          <div className="flex flex-col items-center bg-background/80 backdrop-blur-sm px-2 py-0.5 rounded border border-border/50">
                            <span className="text-[9px] font-mono text-[#FFB000] whitespace-nowrap">Current</span>
                            <span className="text-[10px] font-mono text-[#FFB000] font-bold">${price}</span>
                          </div>
                        </div>
                      </>
                    );
                  })()}
                </div>
              </div>
              {/* Stats */}
              <div className="flex flex-col gap-1 min-w-[200px] border-l dark:border-border/50 border-border pl-4 sm:pl-6 pb-2">
                {(() => {
                  let badgeColor = 'bg-[#f59e0b] text-black border-[#f59e0b] hover:bg-[#f59e0b]/90';
                  let badgeText = (stock.recommendation_key || 'HOLD').replace('_', ' ');
                  const lower = badgeText.toLowerCase();
                  if (lower === 'strong buy') badgeColor = 'bg-[#00d26a] text-black border-[#00d26a] hover:bg-[#00d26a]/90';
                  else if (lower === 'buy') badgeColor = 'bg-[#1db954] text-black border-[#1db954] hover:bg-[#1db954]/90';
                  else if (lower === 'hold') badgeColor = 'bg-[#f59e0b] text-black border-[#f59e0b] hover:bg-[#f59e0b]/90';
                  else if (lower === 'sell') badgeColor = 'bg-[#ef4444] text-white border-[#ef4444] hover:bg-[#ef4444]/90';
                  else if (lower === 'strong sell') badgeColor = 'bg-[#b91c1c] text-white border-[#b91c1c] hover:bg-[#b91c1c]/90';

                  return (
                    <div className="flex items-center gap-3 mb-1">
                      <Badge className={`rounded-[6px] font-mono text-[0.9rem] px-[14px] py-[6px] uppercase ${badgeColor}`}>
                        {badgeText}
                      </Badge>
                      {stock.recommendation_mean && (
                        <span className="text-[0.9rem] font-mono text-foreground font-bold whitespace-nowrap">
                          Score: {Number(stock.recommendation_mean).toFixed(1)}
                        </span>
                      )}
                    </div>
                  );
                })()}
                <div className="text-xs font-mono text-muted-foreground mt-1">
                  Based on {stock.number_of_analyst_opinions} analysts
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Insider Activity */}
      {stock?.insider_transactions?.length > 0 && (
        <Card className="rounded-none border-border dark:bg-card/50 bg-card corner-brackets" data-testid="insider-activity">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-[#FFB000]" /> Insider Activity
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <div className="overflow-x-auto">
              <table className="w-full text-[10px] font-mono">
                <thead>
                  <tr className="border-b border-border text-muted-foreground uppercase tracking-wider">
                    <th className="text-left py-2 pr-3">Date</th>
                    <th className="text-left py-2 pr-3 hidden sm:table-cell">Name</th>
                    <th className="text-left py-2 pr-3 hidden md:table-cell">Title</th>
                    <th className="text-left py-2 pr-3">Type</th>
                    <th className="text-right py-2 pr-3">Shares</th>
                    <th className="text-right py-2">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {stock.insider_transactions.map((tx, i) => {
                    const typeLower = (tx.transaction_type || '').toLowerCase();
                    let typeBadge = <span className="text-muted-foreground">N/A</span>;
                    if (typeLower.includes('buy') || typeLower.includes('purchase')) {
                      typeBadge = <Badge className="bg-[#00d26a] text-black rounded font-mono text-[9px] uppercase hover:bg-[#00d26a]">BUY</Badge>;
                    } else if (typeLower.includes('sell') || typeLower.includes('sale')) {
                      typeBadge = <Badge className="bg-[#ef4444] text-white rounded font-mono text-[9px] uppercase hover:bg-[#ef4444]">SELL</Badge>;
                    } else if (typeLower.includes('award') || typeLower.includes('exercise') || typeLower.includes('withhold')) {
                      typeBadge = <Badge className="bg-[#444] text-white rounded font-mono text-[9px] uppercase hover:bg-[#444]">{tx.transaction_type}</Badge>;
                    } else if (tx.transaction_type && tx.transaction_type !== '--') {
                      typeBadge = <span className="text-muted-foreground">{tx.transaction_type}</span>;
                    }

                    const valueFormatted = tx.value >= 1000000
                      ? `$${(tx.value / 1000000).toFixed(2)}M`
                      : tx.value > 0
                        ? `$${tx.value.toLocaleString()}`
                        : <span className="text-muted-foreground">—</span>;

                    return (
                      <tr key={i} className="border-b border-border/30 hover:bg-muted/10">
                        <td className="py-1.5 pr-3 text-muted-foreground">{tx.date ? new Date(tx.date).toLocaleDateString() : '--'}</td>
                        <td className="py-1.5 pr-3 text-foreground hidden sm:table-cell truncate max-w-[120px]">{tx.insider_name || '--'}</td>
                        <td className="py-1.5 pr-3 text-muted-foreground hidden md:table-cell truncate max-w-[100px]" title="Title as reported in SEC Form 4 filing">
                          {tx.title || '--'}
                        </td>
                        <td className="py-1.5 pr-3">{typeBadge}</td>
                        <td className="py-1.5 pr-3 text-right text-foreground">{tx.shares?.toLocaleString() || '--'}</td>
                        <td className="py-1.5 text-right text-foreground font-data">{valueFormatted}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Top Institutional Holders */}
      {stock?.institutional_holders?.length > 0 && (
        <Card className="rounded-none border-border dark:bg-card/50 bg-card corner-brackets" data-testid="institutional-holders">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
              <Users className="w-4 h-4 text-secondary" /> Top Institutional Holders
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <div className="overflow-x-auto">
              <table className="w-full text-[10px] font-mono">
                <thead>
                  <tr className="border-b border-border text-muted-foreground uppercase tracking-wider">
                    <th className="text-left py-2 pr-3">Holder</th>
                    <th className="text-right py-2 pr-3">Shares</th>
                    <th className="text-right py-2 pr-3">% Held</th>
                    <th className="text-right py-2">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {stock.institutional_holders.map((h, i) => (
                    <tr key={i} className="border-b border-border/30 hover:bg-muted/10">
                      <td className="py-1.5 pr-3 text-foreground truncate max-w-[200px]">{h.holder || '--'}</td>
                      <td className="py-1.5 pr-3 text-right text-foreground">{h.shares?.toLocaleString() || '--'}</td>
                      <td className="py-1.5 pr-3 text-right text-muted-foreground">{h.pct_held ? `${(h.pct_held * 100).toFixed(2)}%` : '--'}</td>
                      <td className="py-1.5 text-right text-foreground">{h.value ? fmt(h.value, { prefix: '$', compact: true }) : '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* News */}
      <Card className="rounded-none border-border dark:bg-card/50 bg-card corner-brackets">
        <CardHeader className="pb-2 pt-3 px-4">
          <CardTitle className="text-sm font-mono uppercase tracking-wider">Recent News for {ticker}</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {news.map((article, i) => (
              <div key={article.article_id || i} data-testid={`stock-news-${i}`}>
                <NewsCard article={article} compact={news.length > 6} />
              </div>
            ))}
          </div>
          {news.length === 0 && <p className="text-xs font-mono text-muted-foreground py-4 text-center">No related news found</p>}
        </CardContent>
      </Card>

      {/* About */}
      {stock?.description && (
        <Card className="rounded-none border-border dark:bg-card/50 bg-card">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-sm font-mono uppercase tracking-wider">About {stock.symbol}</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <p className="text-xs text-muted-foreground leading-relaxed">{stock.description}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
