import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, TrendingDown, Activity, Map, BarChart2 } from 'lucide-react';

import NewsCard from '@/components/NewsCard';
import MarketHeatmap from '@/components/MarketHeatmap';
import EarningsCalendarWidget from '@/components/EarningsCalendarWidget';
import api from '@/lib/api';

function formatPrice(val) {
  if (!val && val !== 0) return '--';
  return typeof val === 'number' ? val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : val;
}

function ChangeDisplay({ change, percent, isVolatility = false }) {
  const isPositive = percent >= 0;
  // VIX increasing is generally "bad" (red), decreasing is "good" (green)
  let colorClass = isPositive ? 'text-[#00FF88] flash-up' : 'text-[#FF4444] flash-down';
  if (isVolatility) {
    colorClass = isPositive ? 'text-[#FF4444] flash-down' : 'text-[#00FF88] flash-up';
  }

  return (
    <span key={`${change}-${percent}`} className={`font-data text-sm flex items-center gap-1 rounded px-1 transition-colors ${colorClass}`}>
      {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {isPositive ? '+' : ''}{formatPrice(change)} ({isPositive ? '+' : ''}{percent?.toFixed(2)}%)
    </span>
  );
}


function SpeedometerGauge({ score, mood }) {
  const normalizedScore = Math.max(0, Math.min(100, Number(score ?? 50)));
  // Determine label and color based on score
  let label = 'NEUTRAL';
  let color = '#eab308'; // yellow
  if (normalizedScore < 25) { label = 'EXTREME FEAR'; color = '#ef4444'; }
  else if (normalizedScore < 45) { label = 'FEAR'; color = '#f97316'; }
  else if (normalizedScore > 75) { label = 'EXTREME GREED'; color = '#22c55e'; }
  else if (normalizedScore > 55) { label = 'GREED'; color = '#84cc16'; }

  // Needle rotation (-90 is left/0, +90 is right/100)
  const angle = -90 + (normalizedScore / 100) * 180;

  return (
    <div className="flex flex-col items-center justify-center w-full relative pt-2">
      <svg viewBox="0 0 200 120" className="w-full max-w-[280px] drop-shadow-md overflow-visible relative">
        <defs>
          <linearGradient id="speedGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ef4444" />
            <stop offset="25%" stopColor="#f97316" />
            <stop offset="50%" stopColor="#eab308" />
            <stop offset="75%" stopColor="#84cc16" />
            <stop offset="100%" stopColor="#22c55e" />
          </linearGradient>
        </defs>

        {/* Track background */}
        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="rgba(255,255,255,0.06)" className="dark:stroke-[rgba(255,255,255,0.06)] stroke-slate-200" strokeWidth="12" strokeLinecap="round" />

        {/* Colored Gradient Arc */}
        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="url(#speedGradient)" strokeWidth="12" strokeLinecap="round" />

        {/* Needle */}
        <g transform={`rotate(${angle} 100 100)`} className="transition-transform duration-1000 ease-out">
          <line x1="100" y1="100" x2="100" y2="25" stroke="var(--color-accent, #00ff88)" strokeWidth="3" strokeLinecap="round" />
          <circle cx="100" cy="100" r="4" fill="var(--color-accent, #00ff88)" />
        </g>

        {/* Zone Labels */}
        <text x="20" y="115" fontSize="9" fill="#ef4444" textAnchor="middle" className="font-mono font-bold tracking-wider">FEAR</text>
        <text x="100" y="115" fontSize="9" fill="#eab308" textAnchor="middle" className="font-mono font-bold tracking-wider">NEUTRAL</text>
        <text x="180" y="115" fontSize="9" fill="#22c55e" textAnchor="middle" className="font-mono font-bold tracking-wider">GREED</text>

        {/* Score Text inside arc */}
        <text x="100" y="80" fontSize="36" fontWeight="800" fill={color} textAnchor="middle" className="font-sans drop-shadow-sm">{normalizedScore}</text>
        <text x="100" y="95" fontSize="11" fill={color} textAnchor="middle" letterSpacing="0.1em" className="font-mono font-bold">{label}</text>
      </svg>

      {/* The Badge logic that existed before is moved up to CardHeader in original container, but we keep this clean here. */}
    </div>
  );
}

export default function Dashboard() {
  const [indices, setIndices] = useState({});
  const [indicesAsOf, setIndicesAsOf] = useState(null);
  const [movers, setMovers] = useState({ gainers: [], losers: [] });
  const [news, setNews] = useState([]);
  const [mood, setMood] = useState({ bullish: 0, bearish: 0, neutral: 0 });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('gainers');
  const [heatmapData, setHeatmapData] = useState(null);
  const [isMarketOpen, setIsMarketOpen] = useState(null);

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

  const moodData = [
    { name: 'Bullish', value: mood.bullish || 1, color: '#00FF41' },
    { name: 'Bearish', value: mood.bearish || 1, color: '#FF3333' },
    { name: 'Neutral', value: mood.neutral || 1, color: '#FFB000' },
  ];

  const indexList = Object.values(indices);
  const activeMovers = activeTab === 'gainers' ? movers.gainers || [] : movers.losers || [];

  return (
    <div className="p-4 lg:p-6 space-y-4 min-h-screen" data-testid="dashboard-page">
      {/* Market Indices Ticker */}
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
        {indicesAsOf && (
          <div className="px-4 pb-2 text-[10px] font-mono text-muted-foreground">
            Data as of (UTC): {indicesAsOf}
          </div>
        )}
      </Card>

      {/* Main Grid: 4 columns on large screens */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">

        {/* Left Column: Top Movers (Gainers / Losers Tabs) */}
        <Card className="rounded-xl dark:border-border/50 border-border shadow-md dark:bg-card/50 bg-card xl:col-span-1 flex flex-col h-[400px]">
          <CardHeader className="pb-0 pt-0 px-0 border-b dark:border-border/50 border-border">
            <div className="flex items-center justify-between px-4 py-2 border-b dark:border-border/20 border-border">
              <span className="text-xs font-mono uppercase tracking-wider font-bold">Top Movers</span>
              {isMarketOpen !== null && (
                <span className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase tracking-wider ${isMarketOpen ? 'bg-[#00FF41]/20 text-[#00FF41]' : 'bg-muted text-muted-foreground'}`}>
                  {isMarketOpen ? '● MARKET OPEN' : 'MARKET CLOSED'}
                </span>
              )}
            </div>
            <div className="flex w-full">
              <button
                onClick={() => setActiveTab('gainers')}
                className={`flex-1 py-3 text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-2 transition-colors ${activeTab === 'gainers' ? 'border-b-2 dark:border-[#00FF41] border-[#059669] dark:text-[#00FF41] text-[#059669]' : 'text-muted-foreground hover:dark:bg-muted/30 hover:bg-muted'}`}
              >
                <TrendingUp className="w-3 h-3" /> Gainers
              </button>
              <button
                onClick={() => setActiveTab('losers')}
                className={`flex-1 py-3 text-xs font-mono uppercase tracking-wider flex items-center justify-center gap-2 transition-colors ${activeTab === 'losers' ? 'border-b-2 border-[#FF3333] text-[#FF3333]' : 'text-muted-foreground hover:dark:bg-muted/30 hover:bg-muted'}`}
              >
                <TrendingDown className="w-3 h-3" /> Losers
              </button>
            </div>
          </CardHeader>
          <CardContent className="p-0 flex-1 overflow-hidden flex flex-col">
            <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: 'thin', scrollbarColor: activeTab === 'gainers' ? '#00FF41 transparent' : '#FF3333 transparent' }}>
              {activeMovers.map((stock) => (
                <Link
                  key={stock.symbol}
                  to={`/stock/${stock.symbol}`}
                  state={{ initialData: stock }}
                  className={`flex items-center justify-between py-2.5 px-4 border-b border-border/10 transition-colors ${activeTab === 'gainers' ? 'hover:dark:bg-[#00FF41]/10 hover:bg-[#059669]/10' : 'hover:dark:bg-[#FF3333]/10 hover:bg-[#FF3333]/10'}`}
                >
                  <div className="min-w-0 pr-2">
                    <span className="font-mono text-xs font-bold text-foreground block truncate">{stock.symbol}</span>
                    <span className="text-[9px] text-muted-foreground truncate block">{stock.name}</span>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <span className="font-data text-xs text-foreground block">${formatPrice(stock.price)}</span>
                    <span className={`font-data text-[10px] ${activeTab === 'gainers' ? 'dark:text-[#00FF41] text-[#059669]' : 'text-[#FF3333]'}`}>
                      {activeTab === 'gainers' ? '+' : ''}{stock.change_percent?.toFixed(2)}%
                    </span>
                  </div>
                </Link>
              ))}
              {activeMovers.length === 0 && !loading && (
                <div className="flex h-full items-center justify-center text-xs text-muted-foreground font-mono">No data</div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Center Columns: Market Heatmap */}
        <Card className="rounded-xl dark:border-border/50 border-border shadow-md dark:bg-card/50 bg-card xl:col-span-2 flex flex-col h-[400px]">
          <CardHeader className="pb-2 pt-3 px-4 border-b dark:border-border/20 border-border">
            <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center justify-between w-full">
              <span className="flex items-center gap-2">
                <Map className="w-4 h-4 text-primary" />
                Market Heatmap
              </span>
              {heatmapData?.last_updated && (
                <span className="text-[10px] text-muted-foreground lowercase tracking-normal font-sans opacity-70">
                  Updated: {new Date(heatmapData.last_updated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 py-4 flex-1 overflow-hidden">
            <MarketHeatmap heatmapData={heatmapData?.sectors || heatmapData} />
          </CardContent>
        </Card>

        {/* Right Column: Market Mood */}
        <Card className="rounded-xl dark:border-border/50 border-border shadow-md dark:bg-card/50 bg-card xl:col-span-1 flex flex-col h-[400px]">
          <CardHeader className="pb-2 pt-3 px-4 border-b dark:border-border/20 border-border">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
                <BarChart2 className="w-4 h-4 text-[#FFB000]" />
                Fear & Greed Index
              </CardTitle>
              {mood.fng_index !== undefined && (
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${mood.dominant === 'bullish' ? 'dark:bg-[#00FF41] bg-[#059669]/20 dark:text-[#00FF41] text-[#059669]' :
                  mood.dominant === 'bearish' ? 'bg-[#FF3333]/20 text-[#FF3333]' : 'bg-[#FFB000]/20 text-[#FFB000]'
                  }`}>
                  {mood.fng_index}/100
                </span>
              )}
            </div>
          </CardHeader>
          <CardContent className="px-4 py-4 flex-1 flex flex-col">
            <div className="flex-1 flex flex-col items-center justify-center min-h-0 mt-4 mb-2">
              <SpeedometerGauge score={mood.fng_index || 50} mood={mood} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mt-4 px-1 pb-1">
              <div className="dark:bg-[rgba(255,255,255,0.03)] bg-slate-50 border dark:border-[rgba(255,255,255,0.08)] border-slate-200 rounded-[8px] p-2 flex flex-col items-center justify-center text-center">
                <span className="text-[9px] text-[#666] uppercase tracking-[0.08em] font-mono mb-1">MARKET MOMENTUM</span>
                <span className={`text-[13px] font-bold font-sans ${mood.dominant === 'bullish' ? 'text-[#22c55e]' : 'text-[#ef4444]'}`}>
                  {mood.dominant === 'bullish' ? '↑ Bullish' : '↓ Bearish'}
                </span>
              </div>
              <div className="dark:bg-[rgba(255,255,255,0.03)] bg-slate-50 border dark:border-[rgba(255,255,255,0.08)] border-slate-200 rounded-[8px] p-2 flex flex-col items-center justify-center text-center">
                <span className="text-[9px] text-[#666] uppercase tracking-[0.08em] font-mono mb-1">VOLATILITY(VIX)</span>
                <span className="text-[13px] font-bold font-sans text-foreground">
                  29.49 (+24%)
                </span>
              </div>
              <div className="dark:bg-[rgba(255,255,255,0.03)] bg-slate-50 border dark:border-[rgba(255,255,255,0.08)] border-slate-200 rounded-[8px] p-2 flex flex-col items-center justify-center text-center">
                <span className="text-[9px] text-[#666] uppercase tracking-[0.08em] font-mono mb-1">MARKET BREADTH</span>
                <span className={`text-[13px] font-bold font-sans text-foreground`}>
                  Bearish: {mood.bearish || 88}%
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

      </div>

      {/* Latest News */}
      <Card className="rounded-xl dark:border-border/50 border-border shadow-md dark:bg-card/50 bg-card">
        <CardHeader className="pb-2 pt-3 px-4 border-b dark:border-border/20 border-border flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
            <Activity className="w-4 h-4 text-secondary" />
            Latest Headlines
            <span className="w-2 h-2 rounded-full bg-primary pulse-live" />
          </CardTitle>
          <Link to="/news" data-testid="view-all-news" className="text-[10px] sm:text-xs font-bold text-primary hover:underline flex items-center">
            View All Recent News
          </Link>
        </CardHeader>
        <CardContent className="px-4 py-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {news.map((article, i) => (
              <div key={article.article_id || i} data-testid={`news-item-${i}`}>
                <NewsCard article={article} compact />
              </div>
            ))}
          </div>
          {news.length === 0 && !loading && (
            <p className="text-xs text-muted-foreground font-mono py-8 text-center">Fetching headlines...</p>
          )}
        </CardContent>
      </Card>

      {/* Earnings Calendar */}
      <div className="mt-4">
        <EarningsCalendarWidget />
      </div>

    </div>
  );
}
