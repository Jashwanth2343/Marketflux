import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Activity, TrendingUp, TrendingDown, AlertTriangle, RefreshCw, Calendar, Globe, BarChart3 } from 'lucide-react';
import api from '@/lib/api';

// --- Yield Curve Chart (simple bar visualization) ---
function YieldCurveChart({ yields, curveLabel, curveColor }) {
  if (!yields || Object.keys(yields).length === 0) return null;
  const maturities = ['3M', '2Y', '5Y', '10Y', '30Y'];
  const available = maturities.filter(m => yields[m] != null);
  const maxY = Math.max(...available.map(m => yields[m])) * 1.15;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">US Treasury Yield Curve</span>
        <Badge variant="outline" className="font-mono text-[9px]" style={{ color: curveColor, borderColor: curveColor + '44' }}>
          {curveLabel}
        </Badge>
      </div>
      <div className="flex items-end gap-2 h-16">
        {available.map((mat) => {
          const val = yields[mat];
          const heightPct = maxY > 0 ? (val / maxY) * 100 : 0;
          return (
            <div key={mat} className="flex flex-col items-center flex-1 gap-1">
              <span className="font-mono text-[9px] text-foreground/70">{val?.toFixed(2)}%</span>
              <div
                className="w-full rounded-none transition-all"
                style={{ height: `${Math.max(8, heightPct)}%`, background: curveColor || '#00F3FF', opacity: 0.8 }}
              />
              <span className="font-mono text-[9px] text-muted-foreground">{mat}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// --- VIX Regime Panel ---
function VixRegimePanel({ vixRegime }) {
  if (!vixRegime) return null;
  const { vix, label, regime, color, playbook = [] } = vixRegime;
  return (
    <div className="p-3 border rounded-none" style={{ borderColor: color + '33', background: color + '08' }}>
      <div className="flex items-center justify-between mb-2">
        <div>
          <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">VIX Regime</p>
          <p className="font-mono text-sm font-bold" style={{ color }}>{label}</p>
        </div>
        <div className="text-right">
          <p className="font-mono text-xl font-black" style={{ color }}>{vix?.toFixed(1)}</p>
          <p className="font-mono text-[9px] text-muted-foreground">VIX</p>
        </div>
      </div>
      {playbook.length > 0 && (
        <div className="space-y-1 mt-2 pt-2 border-t border-border/20">
          {playbook.slice(0, 3).map((tip, i) => (
            <div key={i} className="flex gap-2">
              <span style={{ color }} className="font-mono text-[10px]">→</span>
              <p className="font-mono text-[10px] text-foreground/70 leading-snug">{tip}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Asset Prices Panel ---
function AssetPanel({ assets }) {
  if (!assets) return null;
  const displayAssets = [
    { key: 'SP500', label: 'S&P 500', icon: '📈' },
    { key: 'DXY', label: 'DXY (Dollar)', icon: '💵' },
    { key: 'GOLD', label: 'Gold', icon: '🥇' },
    { key: 'OIL_WTI', label: 'WTI Oil', icon: '🛢️' },
    { key: 'VIX', label: 'VIX', icon: '⚡' },
    { key: 'BITCOIN', label: 'Bitcoin', icon: '₿' },
  ];

  return (
    <div className="grid grid-cols-2 gap-2">
      {displayAssets.map(({ key, label, icon }) => {
        const d = assets[key];
        if (!d) return null;
        const up = (d.change_pct || 0) >= 0;
        return (
          <div key={key} className="p-2 border border-border/30 bg-muted/5 hover:bg-muted/10 transition-colors">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-mono text-[10px] text-muted-foreground">{icon} {label}</span>
                <p className="font-mono text-xs font-bold text-foreground mt-0.5">
                  {d.price != null ? (key === 'BITCOIN' ? `$${(d.price / 1000).toFixed(1)}K` : d.price?.toLocaleString('en-US', { maximumFractionDigits: 2 })) : '--'}
                </p>
              </div>
              <span className={`font-mono text-[10px] font-bold ${up ? 'text-[#3FB950]' : 'text-[#F85149]'}`}>
                {up ? '+' : ''}{d.change_pct?.toFixed(2)}%
              </span>
            </div>
            {d.correlation_note && (
              <p className="font-mono text-[9px] text-muted-foreground/50 mt-1 leading-tight">{d.correlation_note.substring(0, 60)}...</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

// --- Sector Performance Table ---
function SectorTable({ sectors }) {
  if (!sectors || sectors.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border/30">
            <th className="font-mono text-[9px] text-muted-foreground uppercase tracking-wider text-left py-1.5 pr-2">Sector</th>
            <th className="font-mono text-[9px] text-muted-foreground uppercase tracking-wider text-right py-1.5 px-2">1M</th>
            <th className="font-mono text-[9px] text-muted-foreground uppercase tracking-wider text-right py-1.5 px-2">3M</th>
            <th className="font-mono text-[9px] text-muted-foreground uppercase tracking-wider text-right py-1.5 pl-2">Momentum</th>
          </tr>
        </thead>
        <tbody>
          {sectors.map(s => (
            <tr key={s.etf} className="border-b border-border/10 hover:bg-muted/5">
              <td className="font-mono text-[10px] text-foreground py-1.5 pr-2">{s.sector}</td>
              <td className={`font-mono text-[10px] text-right px-2 font-bold ${s.return_1m >= 0 ? 'text-[#3FB950]' : 'text-[#F85149]'}`}>
                {s.return_1m >= 0 ? '+' : ''}{s.return_1m}%
              </td>
              <td className={`font-mono text-[10px] text-right px-2 ${s.return_3m >= 0 ? 'text-[#3FB950]' : 'text-[#F85149]'}`}>
                {s.return_3m >= 0 ? '+' : ''}{s.return_3m}%
              </td>
              <td className="text-right pl-2">
                <span className={`font-mono text-[9px] px-1.5 py-0.5 ${s.momentum_acceleration > 1 ? 'text-[#00FF41] bg-[#00FF41]/10' : s.momentum_acceleration < -1 ? 'text-[#F85149] bg-[#F85149]/10' : 'text-muted-foreground'}`}>
                  {s.momentum_acceleration > 0.5 ? '↑ ACCEL' : s.momentum_acceleration < -0.5 ? '↓ DECEL' : '→ FLAT'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Economic Calendar ---
function EconCalendar({ calendar }) {
  if (!calendar || calendar.length === 0) return null;
  const importanceColor = { CRITICAL: '#F85149', HIGH: '#F0A500', MEDIUM: '#00F3FF' };
  return (
    <div className="space-y-2">
      {calendar.map((ev, i) => (
        <div key={i} className="p-2 border border-border/20 hover:border-border/40 transition-colors">
          <div className="flex items-start justify-between gap-2 mb-1">
            <div>
              <p className="font-mono text-xs font-bold text-foreground">{ev.event}</p>
              <p className="font-mono text-[10px] text-muted-foreground">{ev.date}</p>
            </div>
            <span className="font-mono text-[9px] px-1.5 py-0.5 rounded-none flex-shrink-0"
              style={{ color: importanceColor[ev.importance] || '#888', background: (importanceColor[ev.importance] || '#888') + '15' }}>
              {ev.importance}
            </span>
          </div>
          <p className="font-mono text-[10px] text-foreground/60 leading-snug">{ev.impact_assessment}</p>
        </div>
      ))}
    </div>
  );
}

// --- Main MacroDashboard Page ---
export default function MacroDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const { data: result } = await api.get('/macro/dashboard');
      setData(result);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load macro dashboard');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return (
    <div className="p-4 md:p-6 space-y-4">
      <Skeleton className="h-8 w-48" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-48" />)}
      </div>
    </div>
  );

  if (error) return (
    <div className="p-6 text-center">
      <AlertTriangle className="w-10 h-10 text-destructive mx-auto mb-3" />
      <p className="font-mono text-sm text-destructive">{error}</p>
      <Button onClick={() => load()} variant="outline" className="mt-4 font-mono text-xs uppercase tracking-wider">
        <RefreshCw className="w-3.5 h-3.5 mr-2" /> Retry
      </Button>
    </div>
  );

  const { yield_curve, assets, sectors, vix_regime, fear_greed, economic_calendar, macro_summary, fetched_at } = data || {};

  return (
    <div className="min-h-screen bg-background p-4 md:p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Globe className="w-7 h-7 text-primary" />
          <div>
            <h1 className="font-mono text-xl font-black tracking-tight text-foreground uppercase">Macro Dashboard</h1>
            <p className="font-mono text-[11px] text-muted-foreground">
              Yield Curve • VIX Regime • Sector Rotation • Economic Calendar
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {fetched_at && (
            <span className="font-mono text-[10px] text-muted-foreground hidden md:inline">
              Updated {new Date(fetched_at).toLocaleTimeString()}
            </span>
          )}
          <Button onClick={() => load(true)} disabled={refreshing} variant="outline" size="sm" className="font-mono text-xs uppercase tracking-wider">
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>
      </div>

      {/* Macro Summary Banner */}
      {macro_summary && (
        <div className="mb-6 p-3 border border-[#00F3FF]/20 bg-[#00F3FF]/5">
          <p className="font-mono text-[10px] text-[#00F3FF] uppercase tracking-wider mb-1.5">Macro Intelligence Summary</p>
          <p className="font-mono text-xs text-foreground/80 leading-relaxed">{macro_summary}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Column 1: VIX + Fear & Greed */}
        <div className="space-y-4">
          {vix_regime && <VixRegimePanel vixRegime={vix_regime} />}

          {fear_greed && (
            <Card className="border-border/50 bg-card">
              <CardHeader className="pb-2 border-b border-border/30">
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                  <Activity className="w-3.5 h-3.5 text-primary" /> Fear & Greed Index
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-2xl font-black text-foreground">{fear_greed.value}</span>
                  <Badge variant="outline" className="font-mono text-[10px]">{fear_greed.label}</Badge>
                </div>
                <div className="w-full h-2 bg-gradient-to-r from-[#F85149] via-[#F0A500] via-[#00F3FF] to-[#00FF41] rounded-none">
                  <div className="w-3 h-3 -mt-0.5 bg-white rounded-full shadow transition-all duration-500"
                    style={{ marginLeft: `${(fear_greed.value - 3) / 97 * 100}%` }} />
                </div>
                <div className="flex justify-between mt-1">
                  <span className="font-mono text-[9px] text-[#F85149]">Extreme Fear</span>
                  <span className="font-mono text-[9px] text-[#00FF41]">Extreme Greed</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Yield Curve */}
          {yield_curve && (
            <Card className="border-border/50 bg-card">
              <CardHeader className="pb-2 border-b border-border/30">
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                  <BarChart3 className="w-3.5 h-3.5 text-primary" /> Yield Curve
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-3">
                <YieldCurveChart
                  yields={yield_curve.yields}
                  curveLabel={yield_curve.curve_label}
                  curveColor={yield_curve.curve_color}
                />
                {yield_curve.spread_2s10s != null && (
                  <div className="mt-3 p-2 border border-border/20 bg-muted/5">
                    <p className="font-mono text-[10px] text-muted-foreground">2s10s Spread</p>
                    <p className={`font-mono text-sm font-bold ${yield_curve.spread_2s10s >= 0 ? 'text-[#3FB950]' : 'text-[#F85149]'}`}>
                      {yield_curve.spread_2s10s >= 0 ? '+' : ''}{yield_curve.spread_2s10s?.toFixed(2)}%
                    </p>
                    <p className="font-mono text-[10px] text-muted-foreground/60 mt-1">{yield_curve.curve_interpretation}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Column 2: Asset Prices + Sectors */}
        <div className="space-y-4">
          <Card className="border-border/50 bg-card">
            <CardHeader className="pb-2 border-b border-border/30">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-primary" /> Global Assets
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-3">
              <AssetPanel assets={assets} />
            </CardContent>
          </Card>

          <Card className="border-border/50 bg-card">
            <CardHeader className="pb-2 border-b border-border/30">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-primary" /> Sector Performance
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-3">
              <SectorTable sectors={sectors} />
            </CardContent>
          </Card>
        </div>

        {/* Column 3: Economic Calendar */}
        <div>
          <Card className="border-border/50 bg-card">
            <CardHeader className="pb-2 border-b border-border/30">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                <Calendar className="w-3.5 h-3.5 text-primary" /> Economic Calendar
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-3">
              <EconCalendar calendar={economic_calendar} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
