import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Shield, AlertTriangle, RefreshCw, Activity, BarChart3,
  TrendingUp, TrendingDown, Info
} from 'lucide-react';
import api from '@/lib/api';

// --- Helpers ---
function riskColor(label) {
  if (!label) return '#00F3FF';
  if (label.includes('LOW')) return '#3FB950';
  if (label.includes('MODERATE')) return '#F0A500';
  return '#F85149';
}

function pct(val, d = 2) {
  if (val === null || val === undefined) return '--';
  return `${Number(val).toFixed(d)}%`;
}

function fmt(val, d = 2) {
  if (val === null || val === undefined) return '--';
  return Number(val).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}

// --- Correlation Matrix Heatmap ---
function CorrelationMatrix({ matrix, tickers }) {
  if (!matrix || !tickers || tickers.length === 0) return null;

  function corrColor(v) {
    if (v === null || v === undefined) return 'transparent';
    // -1 → red, 0 → dark, +1 → green
    if (v >= 0.7) return '#F8514920';
    if (v >= 0.4) return '#F0A50020';
    if (v <= -0.4) return '#3FB95020';
    return '#1a1a1a';
  }

  return (
    <div className="overflow-x-auto">
      <table className="text-center border-collapse">
        <thead>
          <tr>
            <th className="font-mono text-[9px] text-muted-foreground p-1 w-12" />
            {tickers.map(t => (
              <th key={t} className="font-mono text-[9px] text-muted-foreground p-1 w-12">{t}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={tickers[i]}>
              <td className="font-mono text-[9px] text-muted-foreground p-1 text-right pr-2">{tickers[i]}</td>
              {row.map((v, j) => (
                <td key={j} className="font-mono text-[9px] p-1 border border-border/10"
                  style={{ background: corrColor(v), color: v === 1 ? '#555' : '#aaa' }}>
                  {v?.toFixed(2)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="font-mono text-[9px] text-muted-foreground/40 mt-1">
        <span className="text-[#F85149]">■</span> High correlation (hidden risk) &nbsp;
        <span className="text-[#3FB950]">■</span> Negative correlation (hedge)
      </p>
    </div>
  );
}

// --- Stress Test Bar Chart ---
function StressTestChart({ stressTests }) {
  if (!stressTests || stressTests.length === 0) return null;
  const worst = Math.min(...stressTests.map(s => s.portfolio_pct_change));
  const best = Math.max(...stressTests.map(s => s.portfolio_pct_change));
  const range = Math.max(Math.abs(worst), Math.abs(best), 5);

  return (
    <div className="space-y-2">
      {stressTests.map(s => {
        const isPosChange = s.portfolio_pct_change >= 0;
        const barWidth = Math.abs(s.portfolio_pct_change) / range * 50;
        return (
          <div key={s.scenario} className="group">
            <div className="flex items-center justify-between mb-0.5">
              <span className="font-mono text-[10px] text-foreground/80">{s.scenario}</span>
              <span className={`font-mono text-[10px] font-bold ${isPosChange ? 'text-[#3FB950]' : 'text-[#F85149]'}`}>
                {isPosChange ? '+' : ''}{s.portfolio_pct_change}%
              </span>
            </div>
            <div className="flex items-center gap-1 h-2">
              {/* Center line */}
              <div className="flex-1 bg-muted/20 h-1 relative">
                <div
                  className="absolute top-0 h-full transition-all duration-500"
                  style={{
                    width: `${barWidth}%`,
                    right: isPosChange ? undefined : `50%`,
                    left: isPosChange ? '50%' : undefined,
                    background: isPosChange ? '#3FB950' : '#F85149',
                  }}
                />
                <div className="absolute top-0 h-full w-px bg-border/60 left-1/2" />
              </div>
            </div>
            <p className="font-mono text-[9px] text-muted-foreground/50 opacity-0 group-hover:opacity-100 transition-opacity">{s.description}</p>
          </div>
        );
      })}
    </div>
  );
}

// --- Factor Exposure Chart ---
function FactorExposure({ factors }) {
  if (!factors) return null;
  const items = [
    { key: 'growth', label: 'Growth', color: '#00F3FF' },
    { key: 'value', label: 'Value', color: '#F0A500' },
    { key: 'quality', label: 'Quality', color: '#00FF41' },
  ];

  return (
    <div className="space-y-2">
      {items.map(({ key, label, color }) => {
        const val = factors[key] || 0;
        const pct = Math.abs(val) * 50; // -1 to +1 → 0 to 50% of bar width
        const positive = val >= 0;
        return (
          <div key={key}>
            <div className="flex justify-between mb-0.5">
              <span className="font-mono text-[10px] text-muted-foreground">{label}</span>
              <span className="font-mono text-[10px]" style={{ color }}>
                {positive ? '+' : ''}{val.toFixed(2)}
              </span>
            </div>
            <div className="flex items-center h-1.5 bg-muted/20 relative">
              <div className="absolute w-px bg-border/50 left-1/2 h-full" />
              <div
                className="absolute h-full transition-all duration-500"
                style={{
                  width: `${pct}%`,
                  [positive ? 'left' : 'right']: '50%',
                  background: color,
                  opacity: 0.8,
                }}
              />
            </div>
          </div>
        );
      })}
      <p className="font-mono text-[9px] text-muted-foreground/50 mt-1">
        Left = Value/Quality tilt · Right = Growth tilt
      </p>
    </div>
  );
}

// --- Holdings Risk Table ---
function HoldingsRiskTable({ holdings }) {
  if (!holdings || holdings.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border/30">
            {['Ticker', 'Weight', 'P&L', 'Beta', 'Max DD', 'Risk'].map(h => (
              <th key={h} className="font-mono text-[9px] text-muted-foreground uppercase tracking-wider text-right first:text-left py-1.5 px-1">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {holdings.map(h => {
            const rc = riskColor(h.risk_sizing?.label || '');
            return (
              <tr key={h.ticker} className="border-b border-border/10 hover:bg-muted/5">
                <td className="font-mono text-xs font-bold text-foreground py-2 px-1">{h.ticker}</td>
                <td className="font-mono text-[10px] text-right text-muted-foreground px-1">{pct(h.weight * 100, 1)}</td>
                <td className={`font-mono text-[10px] text-right px-1 font-bold ${h.pnl_pct >= 0 ? 'text-[#3FB950]' : 'text-[#F85149]'}`}>
                  {h.pnl_pct >= 0 ? '+' : ''}{pct(h.pnl_pct)}
                </td>
                <td className="font-mono text-[10px] text-right text-foreground/80 px-1">{fmt(h.beta)}</td>
                <td className="font-mono text-[10px] text-right text-[#F85149] px-1">
                  {h.risk_sizing ? `-${h.risk_sizing.stop_loss_pct}%` : '--'}
                </td>
                <td className="text-right px-1">
                  <span className="font-mono text-[9px] px-1.5 py-0.5" style={{ color: rc, background: rc + '15' }}>
                    {h.risk_sizing?.label?.split(' ')[0] || '--'}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// --- Single Stock Risk Panel ---
function StockRiskPanel() {
  const [ticker, setTicker] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const analyze = async () => {
    if (!ticker.trim()) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/risk/stock/${ticker.toUpperCase()}`);
      setResult(data);
    } catch (e) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const rc = riskColor(result?.sizing_recommendation?.label || '');

  return (
    <div>
      <div className="flex gap-2 mb-3">
        <input
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          placeholder="Ticker (e.g. AAPL)"
          className="flex-1 font-mono text-xs h-8 bg-background border border-border/50 px-2 focus:outline-none focus:border-primary/50 text-foreground"
          onKeyDown={e => e.key === 'Enter' && analyze()}
        />
        <Button onClick={analyze} disabled={loading || !ticker.trim()} size="sm"
          className="font-mono text-xs uppercase h-8 bg-primary text-black hover:bg-primary/80">
          {loading ? <Activity className="w-3.5 h-3.5 animate-spin" /> : 'Analyze'}
        </Button>
      </div>

      {result && (
        <div className="space-y-3">
          <div className="p-2.5 border rounded-none" style={{ borderColor: rc + '33', background: rc + '08' }}>
            <div className="flex items-center justify-between">
              <p className="font-mono text-sm font-bold text-foreground">{result.ticker}</p>
              <span className="font-mono text-[10px] font-bold" style={{ color: rc }}>
                {result.sizing_recommendation?.label}
              </span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: 'Beta vs SPY', value: fmt(result.beta) },
              { label: '95% Daily VaR', value: result.var_95_daily_pct != null ? `-${fmt(result.var_95_daily_pct)}%` : '--' },
              { label: 'Max Drawdown (1Y)', value: result.max_drawdown_pct != null ? `-${fmt(result.max_drawdown_pct)}%` : '--' },
              { label: 'Ann. Volatility', value: result.annualised_volatility_pct != null ? `${fmt(result.annualised_volatility_pct)}%` : '--' },
              { label: 'Suggested Position', value: result.sizing_recommendation ? `${result.sizing_recommendation.suggested_position_pct}%` : '--' },
              { label: 'Stop Loss', value: result.sizing_recommendation ? `-${result.sizing_recommendation.stop_loss_pct}%` : '--' },
            ].map(({ label, value }) => (
              <div key={label} className="p-1.5 border border-border/20 bg-muted/5">
                <p className="font-mono text-[9px] text-muted-foreground">{label}</p>
                <p className="font-mono text-xs font-bold text-foreground">{value}</p>
              </div>
            ))}
          </div>
          {result.factor_exposure && (
            <div>
              <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Factor Exposure</p>
              <FactorExposure factors={result.factor_exposure} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// --- Main RiskConsole Page ---
export default function RiskConsole() {
  const { user } = useAuth();
  const [portfolioResult, setPortfolioResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const analyzePortfolio = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);

    try {
      // Fetch user's portfolio first
      const { data: portfolioData } = await api.get('/portfolio');
      const holdings = portfolioData?.holdings || [];

      if (holdings.length === 0) {
        setError('No portfolio holdings found. Add stocks to your portfolio first.');
        setLoading(false);
        return;
      }

      const { data } = await api.post('/risk/portfolio', { holdings });
      setPortfolioResult(data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Risk analysis failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (user) analyzePortfolio();
  }, [user, analyzePortfolio]);

  const result = portfolioResult;
  const portBeta = result?.portfolio_beta;
  const betaColor = portBeta == null ? '#00F3FF' : portBeta > 1.3 ? '#F85149' : portBeta > 0.9 ? '#F0A500' : '#3FB950';

  return (
    <div className="min-h-screen bg-background p-4 md:p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Shield className="w-7 h-7 text-primary" />
          <div>
            <h1 className="font-mono text-xl font-black tracking-tight text-foreground uppercase">Risk Console</h1>
            <p className="font-mono text-[11px] text-muted-foreground">
              Portfolio Beta • Correlation Matrix • Stress Tests • Position Sizing
            </p>
          </div>
        </div>
        {user && (
          <Button onClick={analyzePortfolio} disabled={loading} variant="outline" size="sm"
            className="font-mono text-xs uppercase tracking-wider">
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        )}
      </div>

      {!user && (
        <div className="p-6 border border-border/40 bg-card text-center mb-6">
          <Shield className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-40" />
          <p className="font-mono text-sm text-muted-foreground mb-1">Login required to analyze your portfolio risk</p>
          <p className="font-mono text-xs text-muted-foreground/60">Use the single stock risk tool below without login</p>
        </div>
      )}

      {error && !loading && (
        <div className="mb-4 p-3 border border-destructive/30 bg-destructive/5 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-destructive flex-shrink-0" />
          <p className="font-mono text-xs text-destructive">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Main portfolio risk */}
        <div className="lg:col-span-2 space-y-4">
          {/* Portfolio Summary */}
          {(loading || result) && (
            <Card className="border-border/50 bg-card">
              <CardHeader className="pb-2 border-b border-border/30">
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                  <BarChart3 className="w-3.5 h-3.5 text-primary" /> Portfolio Risk Summary
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-3">
                {loading ? (
                  <div className="space-y-2">
                    {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-8" />)}
                  </div>
                ) : result ? (
                  <div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
                      {[
                        { label: 'Portfolio Value', value: `$${result.portfolio_value?.toLocaleString()}` },
                        { label: 'Portfolio Beta', value: fmt(result.portfolio_beta), color: betaColor },
                        { label: '95% VaR (Daily)', value: result.var_95 != null ? `-${fmt(result.var_95)}%` : '--' },
                        { label: 'Max Drawdown', value: result.max_drawdown != null ? `-${fmt(result.max_drawdown)}%` : '--' },
                      ].map(({ label, value, color }) => (
                        <div key={label} className="p-2 border border-border/30 bg-muted/5">
                          <p className="font-mono text-[9px] text-muted-foreground uppercase tracking-wider">{label}</p>
                          <p className="font-mono text-sm font-bold" style={{ color: color || '#fff' }}>{value}</p>
                        </div>
                      ))}
                    </div>

                    {result.risk_summary && (
                      <div className="p-2.5 border border-border/20 bg-muted/5 mb-4">
                        <p className="font-mono text-[10px] text-primary uppercase tracking-wider mb-1">Risk Summary</p>
                        <p className="font-mono text-xs text-foreground/70 leading-relaxed">{result.risk_summary}</p>
                      </div>
                    )}

                    {result.concentration_warning && (
                      <div className="flex items-center gap-2 p-2 border border-[#F0A500]/20 bg-[#F0A500]/5 mb-4">
                        <AlertTriangle className="w-3.5 h-3.5 text-[#F0A500] flex-shrink-0" />
                        <p className="font-mono text-[10px] text-[#F0A500]">{result.concentration_warning}</p>
                      </div>
                    )}

                    <HoldingsRiskTable holdings={result.holdings_detail} />
                  </div>
                ) : null}
              </CardContent>
            </Card>
          )}

          {/* Stress Tests */}
          {result?.stress_tests && (
            <Card className="border-border/50 bg-card">
              <CardHeader className="pb-2 border-b border-border/30">
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                  <AlertTriangle className="w-3.5 h-3.5 text-[#F0A500]" /> Stress Test Scenarios
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-3">
                <StressTestChart stressTests={result.stress_tests} />
              </CardContent>
            </Card>
          )}

          {/* Correlation Matrix */}
          {result?.correlation_matrix?.tickers?.length > 1 && (
            <Card className="border-border/50 bg-card">
              <CardHeader className="pb-2 border-b border-border/30">
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                  <Activity className="w-3.5 h-3.5 text-primary" /> Correlation Matrix
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-3">
                <CorrelationMatrix
                  matrix={result.correlation_matrix.matrix}
                  tickers={result.correlation_matrix.tickers}
                />
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Factor Exposure */}
          {result?.factor_exposure && (
            <Card className="border-border/50 bg-card">
              <CardHeader className="pb-2 border-b border-border/30">
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                  <TrendingUp className="w-3.5 h-3.5 text-primary" /> Factor Exposure
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-3">
                <FactorExposure factors={result.factor_exposure} />
              </CardContent>
            </Card>
          )}

          {/* Sector Concentration */}
          {result?.sector_concentration && (
            <Card className="border-border/50 bg-card">
              <CardHeader className="pb-2 border-b border-border/30">
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                  <BarChart3 className="w-3.5 h-3.5 text-primary" /> Sector Concentration
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-3">
                <div className="space-y-2">
                  {Object.entries(result.sector_concentration).map(([sector, weightPct]) => (
                    <div key={sector}>
                      <div className="flex justify-between mb-0.5">
                        <span className="font-mono text-[10px] text-foreground/80">{sector}</span>
                        <span className={`font-mono text-[10px] font-bold ${weightPct > 40 ? 'text-[#F85149]' : weightPct > 25 ? 'text-[#F0A500]' : 'text-[#3FB950]'}`}>{weightPct}%</span>
                      </div>
                      <div className="w-full bg-muted/20 h-1">
                        <div className="h-full transition-all duration-500"
                          style={{
                            width: `${weightPct}%`,
                            background: weightPct > 40 ? '#F85149' : weightPct > 25 ? '#F0A500' : '#3FB950',
                          }} />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Single Stock Risk */}
          <Card className="border-border/50 bg-card">
            <CardHeader className="pb-2 border-b border-border/30">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                <Info className="w-3.5 h-3.5 text-primary" /> Single Stock Risk
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-3">
              <StockRiskPanel />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
