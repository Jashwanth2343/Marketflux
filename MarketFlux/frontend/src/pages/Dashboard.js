import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { TrendingUp, TrendingDown, Activity, Map, BarChart2, Plane, FlaskConical, Wallet, Bot, Brain, ArrowRight, Zap, Shield, ChevronDown, ChevronUp, CheckCircle2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

import NewsCard from '@/components/NewsCard';
import MarketHeatmap from '@/components/MarketHeatmap';
import EarningsCalendarWidget from '@/components/EarningsCalendarWidget';
import api from '@/lib/api';

function formatPrice(val) {
  if (!val && val !== 0) return '--';
  return typeof val === 'number' ? val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : val;
}

function formatAsOf(raw) {
  if (!raw) return null;
  const d = new Date(raw.endsWith?.('Z') || /[+-]\d{2}:?\d{2}$/.test(raw) ? raw : `${raw}Z`);
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function ChangeDisplay({ change, percent, isVolatility = false }) {
  const isPositive = percent >= 0;
  let colorClass = isPositive ? 'text-gain flash-up' : 'text-loss flash-down';
  if (isVolatility) {
    colorClass = isPositive ? 'text-loss flash-down' : 'text-gain flash-up';
  }

  return (
    <span key={`${change}-${percent}`} className={`font-data text-sm flex items-center gap-1 rounded px-1 transition-colors ${colorClass}`}>
      {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {isPositive ? '+' : ''}{formatPrice(change)} ({isPositive ? '+' : ''}{percent?.toFixed(2)}%)
    </span>
  );
}


function SpeedometerGauge({ score }) {
  const normalizedScore = Math.max(0, Math.min(100, Number(score ?? 50)));
  let label = 'NEUTRAL';
  let color = '#eab308';
  if (normalizedScore < 25) { label = 'EXTREME FEAR'; color = '#ef4444'; }
  else if (normalizedScore < 45) { label = 'FEAR'; color = '#f97316'; }
  else if (normalizedScore > 75) { label = 'EXTREME GREED'; color = '#22c55e'; }
  else if (normalizedScore > 55) { label = 'GREED'; color = '#84cc16'; }

  const angle = -90 + (normalizedScore / 100) * 180;

  return (
    <div className="flex flex-col items-center justify-center w-full relative pt-2">
      <svg viewBox="0 0 200 120" role="img" aria-label={`Fear and Greed index: ${normalizedScore} out of 100, ${label.toLowerCase()}`}
        className="w-full max-w-[280px] drop-shadow-md overflow-visible relative">
        <defs>
          <linearGradient id="speedGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ef4444" />
            <stop offset="25%" stopColor="#f97316" />
            <stop offset="50%" stopColor="#eab308" />
            <stop offset="75%" stopColor="#84cc16" />
            <stop offset="100%" stopColor="#22c55e" />
          </linearGradient>
        </defs>
        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="rgba(255,255,255,0.06)" className="dark:stroke-[rgba(255,255,255,0.06)] stroke-slate-200" strokeWidth="12" strokeLinecap="round" />
        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="url(#speedGradient)" strokeWidth="12" strokeLinecap="round" />
        <g transform={`rotate(${angle} 100 100)`} className="transition-transform duration-1000 ease-out">
          <line x1="100" y1="100" x2="100" y2="25" stroke="hsl(var(--primary))" strokeWidth="3" strokeLinecap="round" />
          <circle cx="100" cy="100" r="4" fill="hsl(var(--primary))" />
        </g>
        <text x="20" y="115" fontSize="9" fill="#ef4444" textAnchor="middle" className="font-mono font-bold tracking-wider">FEAR</text>
        <text x="100" y="115" fontSize="9" fill="#eab308" textAnchor="middle" className="font-mono font-bold tracking-wider">NEUTRAL</text>
        <text x="180" y="115" fontSize="9" fill="#22c55e" textAnchor="middle" className="font-mono font-bold tracking-wider">GREED</text>
        <text x="100" y="80" fontSize="36" fontWeight="800" fill={color} textAnchor="middle" className="font-sans drop-shadow-sm">{normalizedScore}</text>
        <text x="100" y="95" fontSize="11" fill={color} textAnchor="middle" letterSpacing="0.1em" className="font-mono font-bold">{label}</text>
      </svg>
    </div>
  );
}

/* Quiet architectural motif — an exchange-floor colonnade in single-color line
   art. Static and nearly subliminal by design: depth comes from the column
   rhythm, not motion or gradients. */
function ColonnadeMotif() {
  return (
    <svg
      viewBox="0 0 280 120" aria-hidden="true" preserveAspectRatio="xMaxYMax meet"
      className="pointer-events-none absolute right-0 bottom-0 h-full w-auto max-w-[45%] text-primary opacity-[0.07]"
    >
      {/* pediment */}
      <path d="M 10 34 L 140 6 L 270 34" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M 24 38 L 140 13 L 256 38" fill="none" stroke="currentColor" strokeWidth="1" />
      {/* entablature */}
      <line x1="16" y1="44" x2="264" y2="44" stroke="currentColor" strokeWidth="2" />
      {/* columns */}
      {[34, 72, 110, 148, 186, 224, 254].map((x) => (
        <g key={x}>
          <line x1={x} y1="50" x2={x} y2="106" stroke="currentColor" strokeWidth="5" />
          <line x1={x - 7} y1="48" x2={x + 7} y2="48" stroke="currentColor" strokeWidth="2" />
          <line x1={x - 7} y1="109" x2={x + 7} y2="109" stroke="currentColor" strokeWidth="2" />
        </g>
      ))}
      {/* steps */}
      <line x1="8" y1="114" x2="272" y2="114" stroke="currentColor" strokeWidth="2" />
      <line x1="0" y1="119" x2="280" y2="119" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

const CAPABILITIES = [
  {
    to: '/copilot',
    label: 'AI Trading Copilot',
    icon: Plane,
    desc: 'Chat with an AI agent that can research stocks, analyze your portfolio, and execute paper trades autonomously.',
    tag: 'Most Popular',
  },
  {
    to: '/backtest',
    label: 'Strategy Backtester',
    icon: FlaskConical,
    desc: 'Test trading strategies against historical data with walk-forward analysis, Monte Carlo simulations, and AI critique.',
  },
  {
    to: '/intelligence',
    label: 'Market Intelligence',
    icon: Brain,
    desc: 'Real-time news, AI-powered stock screening, macro analysis, and investment thesis builder.',
  },
  {
    to: '/portfolio',
    label: 'Portfolio & Risk',
    icon: Wallet,
    desc: 'Track positions, monitor risk exposure, and get AI-driven rebalancing suggestions.',
  },
];

export default function Dashboard() {
  const { user } = useAuth();
  const [indices, setIndices] = useState({});
  const [indicesAsOf, setIndicesAsOf] = useState(null);
  const [movers, setMovers] = useState({ gainers: [], losers: [] });
  const [news, setNews] = useState([]);
  const [mood, setMood] = useState({ bullish: 0, bearish: 0, neutral: 0 });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('gainers');
  const [heatmapData, setHeatmapData] = useState(null);
  const [isMarketOpen, setIsMarketOpen] = useState(null);
  const [pendingTrades, setPendingTrades] = useState(0);
  // Data-first: market detail is open by default; the collapse choice persists.
  const [showMarketDetail, setShowMarketDetail] = useState(
    () => localStorage.getItem('mf_market_detail') !== 'collapsed'
  );

  const toggleMarketDetail = () => {
    setShowMarketDetail((v) => {
      localStorage.setItem('mf_market_detail', v ? 'collapsed' : 'open');
      return !v;
    });
  };

  useEffect(() => {
    let mounted = true;

    const fetchHeatmapOnly = async () => {
      try {
        const heatmapRes = await api.get('/market/heatmap');
        if (mounted) setHeatmapData(heatmapRes.data);
      } catch (e) {
        console.error('Heatmap fetch error:', e);
      }
    };

    const fetchData = async () => {
      if (mounted) setLoading(true);
      try {
        const [indicesRes, moversRes, newsRes, moodRes, heatmapRes] = await Promise.allSettled([
          api.get('/market/overview'),
          api.get('/market/movers'),
          api.get('/news/feed?limit=8'),
          api.get('/sentiment/mood'),
          api.get('/market/heatmap')
        ]);
        if (mounted) {
          if (indicesRes.status === 'fulfilled') {
            setIndices(indicesRes.value.data.indices || {});
            setIsMarketOpen(indicesRes.value.data.is_market_open);
            setIndicesAsOf(indicesRes.value.data.as_of || null);
          }
          if (moversRes.status === 'fulfilled') setMovers(moversRes.value.data);
          if (newsRes.status === 'fulfilled') setNews(newsRes.value.data.articles || []);
          if (moodRes.status === 'fulfilled') setMood(moodRes.value.data);
          if (heatmapRes.status === 'fulfilled') setHeatmapData(heatmapRes.value.data);
        }
      } catch (e) {
        if (mounted) console.error('Dashboard fetch error:', e);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchHeatmapOnly, 3 * 60 * 1000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  // Staged trades awaiting approval — the operator's most actionable signal.
  useEffect(() => {
    if (!user) return;
    let mounted = true;
    api.get('/copilot/trades/pending')
      .then(({ data }) => { if (mounted) setPendingTrades((data?.items || []).length); })
      .catch(() => { /* backend offline — strip just omits the count */ });
    return () => { mounted = false; };
  }, [user]);

  const indexList = Object.values(indices);
  const activeMovers = activeTab === 'gainers' ? movers.gainers || [] : movers.losers || [];
  const vix = indices['VIX']?.price ?? indices['^VIX']?.price;
  const asOfLabel = formatAsOf(indicesAsOf);

  const operatorStats = [
    {
      label: 'Market',
      value: isMarketOpen === null ? '--' : isMarketOpen ? 'Open' : 'Closed',
      className: isMarketOpen ? 'text-gain' : 'text-muted-foreground',
    },
    {
      label: 'Fear / Greed',
      value: mood.fng_index ? `${mood.fng_index}` : '--',
      className: mood.fng_index > 55 ? 'text-gain' : mood.fng_index < 45 ? 'text-loss' : 'text-primary',
    },
    { label: 'VIX', value: vix ? vix.toFixed(1) : '--', className: 'text-primary' },
  ];

  return (
    <div className="p-4 lg:p-6 space-y-5 min-h-screen" data-testid="dashboard-page">

      {user ? (
        /* ── Operator strip: your state, not a pitch ── */
        <section className="relative overflow-hidden rounded-2xl border border-border/40 bg-card/50">
          <ColonnadeMotif />
          <div className="relative flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <h1 className="text-lg font-semibold text-foreground truncate">
                {`Welcome back${user.name ? `, ${user.name.split(' ')[0]}` : ''}`}
              </h1>
              {pendingTrades > 0 ? (
                <Link to="/copilot" className="mt-1 inline-flex items-center gap-1.5 text-xs text-primary hover:underline">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {pendingTrades === 1 ? '1 staged trade awaiting your approval' : `${pendingTrades} staged trades awaiting your approval`}
                  <ArrowRight className="w-3 h-3" />
                </Link>
              ) : (
                <p className="mt-1 text-xs text-muted-foreground">No approvals pending.</p>
              )}
            </div>
            <div className="flex items-center gap-6">
              {operatorStats.map((s) => (
                <div key={s.label} className="text-center min-w-[64px]">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-0.5">{s.label}</div>
                  <div className={`text-lg font-bold font-mono ${s.className}`}>{s.value}</div>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : (
        /* ── Visitor hero: the pitch belongs here ── */
        <section className="relative overflow-hidden rounded-2xl border border-border/40 bg-card/50">
          <ColonnadeMotif />
          <div className="relative px-5 py-6 sm:px-8 sm:py-8 lg:py-10">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
              <div className="max-w-xl">
                <h1 className="text-2xl sm:text-3xl font-bold text-foreground leading-tight mb-3">
                  Your AI Trading Command Center
                </h1>
                <p className="text-sm text-muted-foreground leading-relaxed max-w-lg">
                  MarketFlux combines real-time market data, AI-powered analysis, and autonomous paper
                  trading into one platform. Research stocks, backtest strategies, and let AI manage a
                  paper portfolio — all without risking real money.
                </p>
                <div className="flex items-center gap-3 mt-5">
                  <Button asChild className="gap-2">
                    <Link to="/copilot">
                      <Plane className="w-4 h-4" />
                      Try the AI Copilot
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </Button>
                  <Button asChild variant="outline" className="gap-2 text-muted-foreground hover:text-foreground">
                    <Link to="/backtest">
                      <FlaskConical className="w-4 h-4" />
                      Run a Backtest
                    </Link>
                  </Button>
                </div>
              </div>
              <div className="flex flex-col gap-2.5 lg:min-w-[220px]">
                {[
                  { icon: Zap, text: 'Real-time market data & AI analysis' },
                  { icon: Bot, text: 'Autonomous paper trading agent' },
                  { icon: Shield, text: 'Paper-only — zero financial risk' },
                ].map(({ icon: Icon, text }) => (
                  <div key={text} className="flex items-center gap-2.5 text-xs text-muted-foreground">
                    <Icon className="w-3.5 h-3.5 text-primary/70 flex-shrink-0" />
                    <span>{text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── Capabilities: tour for visitors, slim quick-nav for operators ── */}
      {user ? (
        <div className="flex flex-wrap gap-2">
          {CAPABILITIES.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="flex items-center gap-2 rounded-lg border border-border/50 bg-card/50 px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
            >
              <Icon className="w-3.5 h-3.5 text-primary/70" />
              {label}
            </Link>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {CAPABILITIES.map(({ to, label, icon: Icon, desc, tag }) => (
            <Link
              key={to}
              to={to}
              className="group relative flex flex-col gap-2 rounded-xl border border-border/50 bg-card/50 px-4 py-4 transition-all hover:border-primary/40 hover:bg-primary/[0.06]"
            >
              {tag && (
                <span className="absolute top-2.5 right-2.5 text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                  {tag}
                </span>
              )}
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/20">
                  <Icon className="w-4 h-4" />
                </span>
                <span className="text-sm font-semibold text-foreground">{label}</span>
              </div>
              <p className="text-[11px] leading-relaxed text-muted-foreground line-clamp-2">{desc}</p>
              <span className="text-[10px] font-mono text-primary/60 group-hover:text-primary flex items-center gap-1 mt-auto">
                Explore <ArrowRight className="w-3 h-3 transition-transform group-hover:translate-x-0.5" />
              </span>
            </Link>
          ))}
        </div>
      )}

      {/* ── Market Indices Ticker ── */}
      <Card className="rounded-xl dark:border-border/50 border-border shadow-md dark:bg-card/50 bg-card overflow-hidden">
        <div className="flex overflow-x-auto py-3 px-4 gap-6">
          {loading && indexList.length === 0 ? (
            Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex-shrink-0 animate-pulse">
                <div className="h-3 w-20 bg-muted mb-1 rounded" />
                <div className="h-4 w-16 bg-muted rounded" />
              </div>
            ))
          ) : (
            indexList.map((idx) => {
              const isVix = idx.symbol === '^VIX';
              return (
                <div key={idx.symbol} className="flex-shrink-0 min-w-[140px]" data-testid={`index-${idx.symbol}`}>
                  <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider block">
                    {idx.name}
                  </span>
                  <span className="font-data text-sm text-foreground">
                    {isVix ? '' : '$'}{formatPrice(idx.price)}
                  </span>
                  <ChangeDisplay change={idx.change} percent={idx.change_percent} isVolatility={isVix} />
                </div>
              );
            })
          )}
        </div>
        {asOfLabel && (
          <div className="px-4 pb-2 text-[10px] font-mono text-muted-foreground">
            Data as of {asOfLabel}
          </div>
        )}
      </Card>

      {/* ── Market Deep Dive toggle ── */}
      <button
        onClick={toggleMarketDetail}
        className="w-full flex items-center justify-center gap-2 py-2 text-xs font-mono text-muted-foreground hover:text-foreground transition-colors"
      >
        {showMarketDetail ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        {showMarketDetail ? 'Collapse market detail' : 'Show heatmap, movers & sentiment'}
      </button>

      {showMarketDetail && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 animate-in fade-in slide-in-from-top-2 duration-300">

          {/* Top Movers */}
          <Card className="rounded-xl dark:border-border/50 border-border shadow-md dark:bg-card/50 bg-card xl:col-span-1 flex flex-col h-[400px]">
            <CardHeader className="pb-0 pt-0 px-0 border-b dark:border-border/50 border-border">
              <div className="flex items-center justify-between px-4 py-2 border-b dark:border-border/20 border-border">
                <span className="text-xs font-mono uppercase tracking-wider font-bold">Top Movers</span>
                {isMarketOpen !== null && (
                  <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider ${isMarketOpen ? 'bg-gain/15 text-gain' : 'bg-muted text-muted-foreground'}`}>
                    {isMarketOpen ? '● MARKET OPEN' : 'MARKET CLOSED'}
                  </span>
                )}
              </div>
              <div className="flex w-full" role="tablist" aria-label="Top movers">
                <button
                  role="tab"
                  aria-selected={activeTab === 'gainers'}
                  onClick={() => setActiveTab('gainers')}
                  className={`flex-1 py-3 text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-2 transition-colors ${activeTab === 'gainers' ? 'border-b-2 border-gain text-gain' : 'text-muted-foreground hover:bg-muted/50'}`}
                >
                  <TrendingUp className="w-3 h-3" /> Gainers
                </button>
                <button
                  role="tab"
                  aria-selected={activeTab === 'losers'}
                  onClick={() => setActiveTab('losers')}
                  className={`flex-1 py-3 text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-2 transition-colors ${activeTab === 'losers' ? 'border-b-2 border-loss text-loss' : 'text-muted-foreground hover:bg-muted/50'}`}
                >
                  <TrendingDown className="w-3 h-3" /> Losers
                </button>
              </div>
            </CardHeader>
            <CardContent className="p-0 flex-1 overflow-hidden flex flex-col">
              <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
                {activeMovers.map((stock) => (
                  <Link
                    key={stock.symbol}
                    to={`/stock/${stock.symbol}`}
                    state={{ initialData: stock }}
                    className={`flex items-center justify-between py-2.5 px-4 border-b border-border/10 transition-colors ${activeTab === 'gainers' ? 'hover:bg-gain/10' : 'hover:bg-loss/10'}`}
                  >
                    <div className="min-w-0 pr-2">
                      <span className="font-mono text-xs font-bold text-foreground block truncate">{stock.symbol}</span>
                      <span className="text-[10px] text-muted-foreground truncate block">{stock.name}</span>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <span className="font-data text-xs text-foreground block">${formatPrice(stock.price)}</span>
                      <span className={`font-data text-[10px] ${activeTab === 'gainers' ? 'text-gain' : 'text-loss'}`}>
                        {activeTab === 'gainers' ? '+' : ''}{stock.change_percent?.toFixed(2)}%
                      </span>
                    </div>
                  </Link>
                ))}
                {loading && activeMovers.length === 0 && (
                  <div className="space-y-0">
                    {Array.from({ length: 8 }).map((_, i) => (
                      <div key={i} className="flex items-center justify-between py-2.5 px-4 border-b border-border/10 animate-pulse">
                        <div className="space-y-1">
                          <div className="h-2.5 w-12 bg-muted rounded" />
                          <div className="h-2 w-20 bg-muted/60 rounded" />
                        </div>
                        <div className="space-y-1 text-right">
                          <div className="h-2.5 w-14 bg-muted rounded" />
                          <div className="h-2 w-10 bg-muted/60 rounded ml-auto" />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {activeMovers.length === 0 && !loading && (
                  <div className="flex flex-col h-full items-center justify-center gap-2 text-center px-4">
                    <span className="text-2xl">📊</span>
                    <p className="text-xs font-mono text-muted-foreground">Market data unavailable</p>
                    <p className="text-[10px] text-muted-foreground/70 font-mono">Check back during market hours</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Market Heatmap */}
          <Card className="rounded-xl dark:border-border/50 border-border shadow-md dark:bg-card/50 bg-card xl:col-span-2 flex flex-col h-[400px]">
            <CardHeader className="pb-2 pt-3 px-4 border-b dark:border-border/20 border-border">
              <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center justify-between w-full">
                <span className="flex items-center gap-2">
                  <Map className="w-4 h-4 text-primary" />
                  Market Heatmap
                </span>
                {heatmapData?.last_updated && (
                  <span className="text-[10px] text-muted-foreground lowercase tracking-normal font-sans">
                    Updated {new Date(heatmapData.last_updated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 py-4 flex-1 overflow-hidden">
              <MarketHeatmap heatmapData={heatmapData?.sectors || heatmapData} />
            </CardContent>
          </Card>

          {/* Fear & Greed */}
          <Card className="rounded-xl dark:border-border/50 border-border shadow-md dark:bg-card/50 bg-card xl:col-span-1 flex flex-col h-[400px]">
            <CardHeader className="pb-2 pt-3 px-4 border-b dark:border-border/20 border-border">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
                  <BarChart2 className="w-4 h-4 text-primary" />
                  Fear & Greed Index
                </CardTitle>
                {mood.fng_index !== undefined && (
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${mood.dominant === 'bullish' ? 'bg-gain/15 text-gain' :
                    mood.dominant === 'bearish' ? 'bg-loss/15 text-loss' : 'bg-primary/15 text-primary'
                    }`}>
                    {mood.fng_index}/100
                  </span>
                )}
              </div>
            </CardHeader>
            <CardContent className="px-4 py-4 flex-1 flex flex-col">
              <div className="flex-1 flex flex-col items-center justify-center min-h-0 mt-4 mb-2">
                <SpeedometerGauge score={mood.fng_index || 50} />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mt-4 px-1 pb-1">
                <div className="bg-muted/30 border border-border rounded-lg p-2 flex flex-col items-center justify-center text-center">
                  <span className="text-[10px] text-muted-foreground uppercase tracking-[0.08em] font-mono mb-1">Momentum</span>
                  <span className={`text-[13px] font-bold font-sans ${
                    mood.dominant === 'bullish' ? 'text-gain' : mood.dominant === 'bearish' ? 'text-loss' : 'text-primary'
                  }`}>
                    {mood.dominant === 'bullish' ? '↑ Bullish' : mood.dominant === 'bearish' ? '↓ Bearish' : '→ Neutral'}
                  </span>
                </div>
                <div className="bg-muted/30 border border-border rounded-lg p-2 flex flex-col items-center justify-center text-center">
                  <span className="text-[10px] text-muted-foreground uppercase tracking-[0.08em] font-mono mb-1">Volatility</span>
                  <span className="text-[13px] font-bold font-sans text-foreground">
                    {vix ? vix.toFixed(1) : '--'}
                  </span>
                </div>
                <div className="bg-muted/30 border border-border rounded-lg p-2 flex flex-col items-center justify-center text-center">
                  <span className="text-[10px] text-muted-foreground uppercase tracking-[0.08em] font-mono mb-1">News Breadth</span>
                  <span className="text-[13px] font-bold font-sans">
                    <span className="text-gain">{mood.bullish ?? 0}↑</span>
                    <span className="text-muted-foreground mx-1">/</span>
                    <span className="text-loss">{mood.bearish ?? 0}↓</span>
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── Latest News ── */}
      <Card className="rounded-xl dark:border-border/50 border-border shadow-md dark:bg-card/50 bg-card">
        <CardHeader className="pb-2 pt-3 px-4 border-b dark:border-border/20 border-border flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
            <Activity className="w-4 h-4 text-secondary" />
            Latest Headlines
          </CardTitle>
          <Link to="/intelligence?tab=news" data-testid="view-all-news" className="text-[10px] sm:text-xs font-bold text-primary hover:underline flex items-center">
            View All Recent News
          </Link>
        </CardHeader>
        <CardContent className="px-4 py-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {news.slice(0, 4).map((article, i) => (
              <div key={article.article_id || i} data-testid={`news-item-${i}`}>
                <NewsCard article={article} compact />
              </div>
            ))}
          </div>
          {news.length === 0 && (loading ? (
            <p className="text-xs text-muted-foreground font-mono py-8 text-center">Fetching headlines...</p>
          ) : (
            <p className="text-xs text-muted-foreground font-mono py-8 text-center">
              No headlines right now — <Link to="/intelligence?tab=news" className="text-primary hover:underline">try the full news feed</Link>.
            </p>
          ))}
        </CardContent>
      </Card>

      {/* ── Earnings Calendar ── */}
      <EarningsCalendarWidget />

    </div>
  );
}
