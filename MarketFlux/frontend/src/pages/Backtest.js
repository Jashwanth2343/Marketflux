import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import {
    FlaskConical, Play, BarChart3, TrendingUp, TrendingDown, AlertTriangle,
    Loader2, Code, Layers, X, Plus, Save, Trash2, Download, Copy, Check,
    Brain, Sparkles, ChevronDown, ChevronUp, RefreshCw, ArrowUpDown,
    ChevronLeft, ChevronRight, Zap, Shield, Target, Clock, Award, Activity,
    Terminal, Share2, Eye, EyeOff,
    FileText, Wand2, Lightbulb,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import {
    getExampleStrategy, runBacktest, runWalkForward, fetchBenchmark,
    runMonteCarlo, aiCritique, aiParseStrategy, fetchMarketContext,
} from '@/lib/backtestApi';
import {
    AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid,
    Tooltip as RechartsTooltip, ResponsiveContainer, Legend,
} from 'recharts';

// ─── Constants ────────────────────────────────────────────────────────────────

const INDICATOR_TYPES = [
    { value: 'sma', label: 'SMA', params: ['period', 'source'] },
    { value: 'ema', label: 'EMA', params: ['period', 'source'] },
    { value: 'rsi', label: 'RSI', params: ['period', 'source'] },
    { value: 'macd', label: 'MACD', params: ['fast', 'slow', 'signal', 'source'] },
    { value: 'macd_signal', label: 'MACD Signal', params: ['fast', 'slow', 'signal', 'source'] },
    { value: 'bollinger_upper', label: 'Bollinger Upper', params: ['period', 'num_std', 'source'] },
    { value: 'bollinger_lower', label: 'Bollinger Lower', params: ['period', 'num_std', 'source'] },
    { value: 'atr', label: 'ATR', params: ['period'] },
    { value: 'returns', label: 'Returns', params: ['period', 'source'] },
    { value: 'rolling_high', label: 'Rolling High', params: ['period', 'source'] },
    { value: 'rolling_low', label: 'Rolling Low', params: ['period', 'source'] },
    { value: 'volume_sma', label: 'Volume SMA', params: ['period'] },
];

const COMPARATORS = [
    { value: 'gt', label: '>' },
    { value: 'gte', label: '>=' },
    { value: 'lt', label: '<' },
    { value: 'lte', label: '<=' },
    { value: 'eq', label: '==' },
    { value: 'neq', label: '!=' },
    { value: 'crosses_above', label: 'Crosses Above' },
    { value: 'crosses_below', label: 'Crosses Below' },
];

const SIZING_TYPES = [
    { value: 'fixed_pct', label: 'Fixed %' },
    { value: 'fixed_dollar', label: 'Fixed $' },
    { value: 'equal_weight', label: 'Equal Weight' },
];

const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

const LOADING_STAGES = [
    'Fetching market data…',
    'Running strategy logic…',
    'Computing metrics…',
    'Finalizing results…',
];

const STORAGE_KEY = 'backtest_saved_strategies';

const COMMUNITY_TEMPLATES = [
    {
        name: "RSI Mean Reversion",
        description: "Buy oversold (RSI<30) above 200 SMA, exit when RSI>65",
        risk: "Medium",
        asset: "US Large Cap",
        strategy: { name: "RSI Mean Reversion", universe: ["AAPL","MSFT","NVDA"], indicators: { rsi14: {type:"rsi",period:14}, sma200: {type:"sma",period:200} }, entry: { all: [{lt:["rsi14",30]},{gt:["close","sma200"]}] }, exit: { any: [{gt:["rsi14",65]},{hold_days_gte:20}] }, position_sizing:{type:"fixed_pct",pct:0.1}, max_positions:5, stop_loss_pct:0.08, take_profit_pct:0.20 }
    },
    {
        name: "Golden Cross",
        description: "Buy when 50 SMA crosses above 200 SMA, sell on death cross",
        risk: "Low",
        asset: "Index / ETF",
        strategy: { name: "Golden Cross", universe: ["SPY","QQQ"], indicators: { sma50:{type:"sma",period:50}, sma200:{type:"sma",period:200} }, entry: { all: [{crosses_above:["sma50","sma200"]}] }, exit: { any: [{crosses_below:["sma50","sma200"]}] }, position_sizing:{type:"fixed_pct",pct:0.25}, max_positions:2, stop_loss_pct:0.10, take_profit_pct:null }
    },
    {
        name: "Bollinger Band Squeeze",
        description: "Buy when price touches lower band, sell at upper band",
        risk: "Medium",
        asset: "US Large Cap",
        strategy: { name: "Bollinger Squeeze", universe: ["AAPL","GOOGL","AMZN"], indicators: { bb_lower:{type:"bollinger_lower",period:20,num_std:2}, bb_upper:{type:"bollinger_upper",period:20,num_std:2} }, entry: { all: [{lte:["close","bb_lower"]}] }, exit: { any: [{gte:["close","bb_upper"]},{hold_days_gte:15}] }, position_sizing:{type:"fixed_pct",pct:0.10}, max_positions:5, stop_loss_pct:0.05, take_profit_pct:0.15 }
    },
    {
        name: "Momentum (12-1)",
        description: "Buy stocks with highest 12-month returns, rebalance monthly",
        risk: "High",
        asset: "US Large Cap",
        strategy: { name: "12-1 Momentum", universe: ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA"], indicators: { ret252:{type:"returns",period:252}, sma50:{type:"sma",period:50} }, entry: { all: [{gt:["ret252",0.10]},{gt:["close","sma50"]}] }, exit: { any: [{lt:["ret252",-0.05]},{hold_days_gte:22}] }, position_sizing:{type:"equal_weight"}, max_positions:3, stop_loss_pct:0.12, take_profit_pct:0.30 }
    },
    {
        name: "Turtle Breakout",
        description: "Buy at 20-day high, sell at 10-day low with trailing stop",
        risk: "High",
        asset: "Multi-Asset",
        strategy: { name: "Turtle Breakout", universe: ["SPY","GLD","TLT","USO"], indicators: { high20:{type:"rolling_high",period:20}, low10:{type:"rolling_low",period:10}, atr14:{type:"atr",period:14} }, entry: { all: [{gte:["close","high20"]}] }, exit: { any: [{lte:["close","low10"]}] }, position_sizing:{type:"fixed_pct",pct:0.15}, max_positions:4, stop_loss_pct:0.10, take_profit_pct:null }
    },
    {
        name: "MACD Crossover",
        description: "Buy on MACD signal crossover, exit on reverse cross",
        risk: "Medium",
        asset: "US Large Cap",
        strategy: { name: "MACD Crossover", universe: ["AAPL","MSFT","NVDA","GOOGL"], indicators: { macd_line:{type:"macd",fast:12,slow:26}, macd_sig:{type:"macd_signal",fast:12,slow:26,signal:9} }, entry: { all: [{crosses_above:["macd_line","macd_sig"]}] }, exit: { any: [{crosses_below:["macd_line","macd_sig"]}] }, position_sizing:{type:"fixed_pct",pct:0.12}, max_positions:4, stop_loss_pct:0.07, take_profit_pct:0.20 }
    },
    {
        name: "Volatility-Adjusted Trend",
        description: "Follow EMA trend with ATR-based position sizing filter",
        risk: "Medium",
        asset: "US Large Cap",
        strategy: { name: "Vol-Adjusted Trend", universe: ["AAPL","MSFT","JPM","JNJ","XOM"], indicators: { ema21:{type:"ema",period:21}, ema55:{type:"ema",period:55}, atr14:{type:"atr",period:14} }, entry: { all: [{gt:["ema21","ema55"]},{gt:["close","ema21"]}] }, exit: { any: [{lt:["ema21","ema55"]},{hold_days_gte:30}] }, position_sizing:{type:"fixed_pct",pct:0.10}, max_positions:5, stop_loss_pct:0.06, take_profit_pct:0.18 }
    },
    {
        name: "Earnings Drift",
        description: "Post-earnings momentum play (needs earnings data — placeholder)",
        risk: "High",
        asset: "US Large Cap",
        strategy: { name: "Earnings Drift", universe: ["AAPL","NVDA","TSLA"], indicators: { ret5:{type:"returns",period:5}, vol_sma:{type:"volume_sma",period:20} }, entry: { all: [{gt:["ret5",0.03]},{gt:["volume","vol_sma"]}] }, exit: { any: [{hold_days_gte:15},{lt:["ret5",-0.03]}] }, position_sizing:{type:"fixed_pct",pct:0.08}, max_positions:5, stop_loss_pct:0.05, take_profit_pct:0.15 }
    },
];

const METRIC_DEFS = [
    { key: 'total_return', label: 'Total Return', type: 'pct', icon: TrendingUp, tip: 'Total portfolio return over the full period', thresholds: [0.5, 0.1, 0] },
    { key: 'cagr', label: 'CAGR', type: 'pct', icon: TrendingUp, tip: 'Compound annual growth rate', thresholds: [0.2, 0.08, 0] },
    { key: 'sharpe', label: 'Sharpe Ratio', type: 'ratio', icon: BarChart3, tip: 'Risk-adjusted return (annualized). >1 good, >2 excellent', thresholds: [2, 1, 0.5] },
    { key: 'sortino', label: 'Sortino Ratio', type: 'ratio', icon: BarChart3, tip: 'Downside risk-adjusted return. Higher is better', thresholds: [2.5, 1.2, 0.5] },
    { key: 'max_drawdown', label: 'Max Drawdown', type: 'pct', icon: TrendingDown, tip: 'Largest peak-to-trough decline', thresholds: null, invertColor: true },
    { key: 'calmar', label: 'Calmar Ratio', type: 'ratio', icon: Shield, tip: 'CAGR / Max Drawdown. >1 is acceptable, >3 excellent', thresholds: [3, 1, 0.5] },
    { key: 'win_rate', label: 'Win Rate', type: 'pct', icon: Target, tip: 'Percentage of profitable trades', thresholds: [0.6, 0.45, 0.35] },
    { key: 'profit_factor', label: 'Profit Factor', type: 'ratio', icon: Zap, tip: 'Gross profit / gross loss. >1.5 good, >2 excellent', thresholds: [2, 1.5, 1] },
    { key: 'expectancy', label: 'Expectancy', type: 'money', icon: Award, tip: 'Average expected P&L per trade', thresholds: null },
    { key: 'avg_trade_duration', label: 'Avg Duration', type: 'days', icon: Clock, tip: 'Average number of days a trade is held', thresholds: null },
    { key: 'best_trade', label: 'Best Trade', type: 'pct', icon: TrendingUp, tip: 'Largest single-trade return', thresholds: null },
    { key: 'worst_trade', label: 'Worst Trade', type: 'pct', icon: TrendingDown, tip: 'Largest single-trade loss', thresholds: null, invertColor: true },
];

// ─── Utility Functions ────────────────────────────────────────────────────────

function defaultStrategy() {
    return {
        name: '',
        universe: ['AAPL'],
        indicators: {},
        entry: { all: [] },
        exit: { any: [] },
        position_sizing: { type: 'fixed_pct', pct: 0.1 },
        max_positions: 5,
        stop_loss_pct: 0.08,
        take_profit_pct: 0.20,
    };
}

function fmt(v, type = 'pct') {
    if (v == null || isNaN(v)) return '—';
    if (type === 'pct') return `${(v * 100).toFixed(2)}%`;
    if (type === 'ratio') return v.toFixed(2);
    if (type === 'money') return `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (type === 'int') return Math.round(v).toLocaleString();
    if (type === 'days') return `${Math.round(v)}d`;
    return String(v);
}

function metricColor(def, value) {
    if (value == null || isNaN(value)) return 'text-muted-foreground';
    if (def.invertColor) {
        const abs = Math.abs(value);
        if (abs < 0.1) return 'text-green-400';
        if (abs < 0.25) return 'text-amber-400';
        return 'text-red-400';
    }
    if (def.thresholds) {
        const [high, mid, low] = def.thresholds;
        if (value >= high) return 'text-green-400';
        if (value >= mid) return 'text-amber-400';
        if (value >= low) return 'text-orange-400';
        return 'text-red-400';
    }
    if (value > 0) return 'text-green-400';
    if (value < 0) return 'text-red-400';
    return 'text-foreground';
}

function deriveMetrics(metrics, trades) {
    if (!metrics) return {};
    const derived = { ...metrics };
    if (derived.calmar == null && derived.cagr != null && derived.max_drawdown) {
        derived.calmar = Math.abs(derived.max_drawdown) > 0.0001 ? derived.cagr / Math.abs(derived.max_drawdown) : 0;
    }
    if (trades?.length) {
        const returns = trades.map(t => t.return_pct).filter(r => r != null);
        if (returns.length) {
            derived.best_trade = derived.best_trade ?? Math.max(...returns);
            derived.worst_trade = derived.worst_trade ?? Math.min(...returns);
        }
        const durations = trades.map(t => t.bars_held).filter(b => b != null);
        if (durations.length) {
            derived.avg_trade_duration = derived.avg_trade_duration ?? (durations.reduce((a, b) => a + b, 0) / durations.length);
        }
    }
    return derived;
}

function loadSavedStrategies() {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    } catch { return []; }
}

function saveSavedStrategies(list) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

function riskBadgeClass(risk) {
    if (risk === 'Low') return 'bg-green-500/15 text-green-400 border-green-500/30';
    if (risk === 'Medium') return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
    return 'bg-red-500/15 text-red-400 border-red-500/30';
}

function encodeStrategyUrl(strategy, startDate, endDate) {
    try {
        const payload = { strategy, start: startDate, end: endDate };
        return window.btoa(JSON.stringify(payload));
    } catch { return null; }
}

function decodeStrategyUrl(encoded) {
    try {
        return JSON.parse(window.atob(encoded));
    } catch { return null; }
}

function generatePythonCode(strategy, startDate, endDate, capital) {
    const tickers = strategy.universe?.join("', '") || 'AAPL';
    const indLines = Object.entries(strategy.indicators || {}).map(([name, spec]) => {
        if (spec.type === 'sma') return `        self.${name} = bt.indicators.SMA(self.data.close, period=${spec.period || 20})`;
        if (spec.type === 'ema') return `        self.${name} = bt.indicators.EMA(self.data.close, period=${spec.period || 20})`;
        if (spec.type === 'rsi') return `        self.${name} = bt.indicators.RSI(self.data.close, period=${spec.period || 14})`;
        if (spec.type === 'macd') return `        self.${name} = bt.indicators.MACD(self.data.close, period_me1=${spec.fast || 12}, period_me2=${spec.slow || 26})`;
        if (spec.type === 'atr') return `        self.${name} = bt.indicators.ATR(self.data, period=${spec.period || 14})`;
        if (spec.type === 'bollinger_upper' || spec.type === 'bollinger_lower') return `        self.bb = bt.indicators.BollingerBands(self.data.close, period=${spec.period || 20}, devfactor=${spec.num_std || 2})`;
        return `        # self.${name} = ... (${spec.type} — implement manually)`;
    });
    return `import backtrader as bt
import datetime

class ${(strategy.name || 'MyStrategy').replace(/[^a-zA-Z0-9]/g, '')}(bt.Strategy):
    \"\"\"Auto-generated from MarketFlux Backtest Lab\"\"\"

    def __init__(self):
${indLines.join('\n') || '        pass'}

    def next(self):
        # Entry / exit logic — adapt conditions from your DSL
        if not self.position:
            # TODO: implement entry conditions
            pass
        else:
            # TODO: implement exit conditions
            pass

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    cerebro.addstrategy(${(strategy.name || 'MyStrategy').replace(/[^a-zA-Z0-9]/g, '')})

    for ticker in ['${tickers}']:
        data = bt.feeds.YahooFinanceData(
            dataname=ticker,
            fromdate=datetime.datetime(${startDate.split('-').join(', ')}),
            todate=datetime.datetime(${endDate.split('-').join(', ')}),
        )
        cerebro.adddata(data, name=ticker)

    cerebro.broker.setcash(${capital})
    cerebro.addsizer(bt.sizers.PercentSizer, percents=${((strategy.position_sizing?.pct || 0.1) * 100).toFixed(0)})

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.plot()
`;
}

function exportTradesCsv(trades) {
    if (!trades?.length) return;
    const headers = ['Symbol','Entry Date','Exit Date','Entry Price','Exit Price','Shares','P&L','Return %','Bars Held','Exit Reason'];
    const rows = trades.map(t => [
        t.symbol, t.entry_date?.slice(0, 10), t.exit_date?.slice(0, 10),
        t.entry_price?.toFixed(2), t.exit_price?.toFixed(2), Math.round(t.shares),
        t.pnl?.toFixed(2), ((t.return_pct || 0) * 100).toFixed(2), t.bars_held, t.exit_reason || '',
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'backtest_trades.csv'; a.click();
    URL.revokeObjectURL(url);
}

// ─── Market Context Ribbon ────────────────────────────────────────────────────

function MarketContextRibbon() {
    const [ctx, setCtx] = useState(null);

    useEffect(() => {
        fetchMarketContext().then(setCtx).catch(() => {});
    }, []);

    if (!ctx) return null;

    const trendColor = ctx.spy_trend === 'Bullish' ? 'text-green-400' :
                        ctx.spy_trend === 'Bearish' ? 'text-red-400' : 'text-amber-400';
    const vixColor = ctx.vix > 25 ? 'text-red-400' : ctx.vix > 18 ? 'text-amber-400' : 'text-green-400';

    return (
        <div className="flex items-center gap-6 px-4 py-2 rounded-lg bg-white/[0.02] border border-white/10 text-xs font-mono mb-4 overflow-x-auto">
            <span className="text-muted-foreground flex items-center gap-1.5">
                <Activity className="w-3 h-3" />LIVE MARKET
            </span>
            <span className="flex items-center gap-1">
                <span className="text-muted-foreground">SPY</span>
                <span className="text-foreground">${ctx.spy_price?.toFixed(2)}</span>
            </span>
            <span className="flex items-center gap-1">
                <span className="text-muted-foreground">Trend</span>
                <span className={trendColor}>{ctx.spy_trend}</span>
            </span>
            <span className="flex items-center gap-1">
                <span className="text-muted-foreground">VIX</span>
                <span className={vixColor}>{ctx.vix?.toFixed(1)}</span>
            </span>
            <span className="flex items-center gap-1">
                <span className="text-muted-foreground">50 MA</span>
                <span className="text-foreground">${ctx.spy_50ma?.toFixed(2)}</span>
            </span>
            <span className="flex items-center gap-1">
                <span className="text-muted-foreground">200 MA</span>
                <span className="text-foreground">${ctx.spy_200ma?.toFixed(2)}</span>
            </span>
        </div>
    );
}

// ─── AI Strategy Builder ──────────────────────────────────────────────────────

function AiStrategyBuilder({ onApply }) {
    const [desc, setDesc] = useState('');
    const [loading, setLoading] = useState(false);
    const [preview, setPreview] = useState(null);

    // Pick up a strategy handed off from the Strategy Studio ("Backtest" button).
    useEffect(() => {
        const seed = sessionStorage.getItem('backtest_seed');
        if (seed) { setDesc(seed); sessionStorage.removeItem('backtest_seed'); }
    }, []);

    const handleParse = useCallback(async () => {
        if (!desc.trim()) return;
        setLoading(true);
        try {
            const parsed = await aiParseStrategy({ description: desc });
            setPreview(parsed);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'AI parsing failed');
        } finally {
            setLoading(false);
        }
    }, [desc]);

    return (
        <div className="rounded-xl border border-white/10 bg-gradient-to-br from-primary/5 to-transparent p-4 space-y-3">
            <div className="flex items-center gap-2">
                <Wand2 className="w-4 h-4 text-primary" />
                <span className="text-xs font-mono font-semibold text-foreground uppercase tracking-wider">AI Strategy Builder</span>
            </div>
            <textarea
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                placeholder="Describe your strategy in plain English… e.g. 'Buy when RSI drops below 30 and price is above the 200-day moving average. Sell when RSI rises above 70. Use 10% position sizing with a 5% stop loss.'"
                rows={3}
                className="w-full px-3 py-2 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none"
            />
            <div className="flex items-center gap-2">
                <Button size="sm" onClick={handleParse} disabled={loading || !desc.trim()} className="text-xs font-mono gap-1.5">
                    {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                    Parse Strategy
                </Button>
                {preview && (
                    <Button size="sm" variant="outline" onClick={() => { onApply(preview); setPreview(null); setDesc(''); toast.success('AI strategy applied'); }} className="text-xs font-mono gap-1.5">
                        <Check className="w-3 h-3" />Apply
                    </Button>
                )}
            </div>
            {preview && (
                <pre className="text-xs font-mono text-green-400/80 bg-black/30 rounded p-3 max-h-48 overflow-auto border border-white/5">
                    {JSON.stringify(preview, null, 2)}
                </pre>
            )}
        </div>
    );
}

// ─── Strategy Library ─────────────────────────────────────────────────────────

function StrategyLibrary({ onApply, currentStrategy }) {
    const [saved, setSaved] = useState(() => loadSavedStrategies());
    const [tab, setTab] = useState('templates');
    const [saveName, setSaveName] = useState('');

    const handleSave = () => {
        const name = saveName.trim() || currentStrategy.name || `Strategy ${saved.length + 1}`;
        const entry = { name, strategy: currentStrategy, savedAt: new Date().toISOString(), metrics: null };
        const next = [entry, ...saved.filter(s => s.name !== name)];
        setSaved(next);
        saveSavedStrategies(next);
        setSaveName('');
        toast.success(`Saved "${name}"`);
    };

    const handleDelete = (name) => {
        const next = saved.filter(s => s.name !== name);
        setSaved(next);
        saveSavedStrategies(next);
        toast.success(`Deleted "${name}"`);
    };

    return (
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
            <Tabs value={tab} onValueChange={setTab}>
                <TabsList className="bg-white/5 mb-3">
                    <TabsTrigger value="templates" className="text-xs font-mono">Templates</TabsTrigger>
                    <TabsTrigger value="my" className="text-xs font-mono">My Strategies</TabsTrigger>
                </TabsList>

                <TabsContent value="templates">
                    <div className="grid grid-cols-1 gap-2 max-h-64 overflow-y-auto pr-1">
                        {COMMUNITY_TEMPLATES.map((t) => (
                            <button
                                key={t.name}
                                onClick={() => onApply(t.strategy)}
                                className="text-left p-3 rounded-lg border border-white/5 bg-white/[0.02] hover:bg-white/[0.05] transition-colors group"
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-sm font-mono font-semibold text-foreground">{t.name}</span>
                                    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${riskBadgeClass(t.risk)}`}>{t.risk}</span>
                                </div>
                                <p className="text-xs text-muted-foreground font-mono leading-relaxed">{t.description}</p>
                                <span className="text-[10px] text-muted-foreground/60 font-mono mt-1 block">{t.asset}</span>
                            </button>
                        ))}
                    </div>
                </TabsContent>

                <TabsContent value="my">
                    <div className="flex gap-2 mb-3">
                        <input
                            value={saveName}
                            onChange={(e) => setSaveName(e.target.value)}
                            placeholder="Strategy name…"
                            className="flex-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                            onKeyDown={(e) => e.key === 'Enter' && handleSave()}
                        />
                        <Button size="sm" variant="outline" onClick={handleSave} className="text-xs font-mono gap-1">
                            <Save className="w-3 h-3" />Save
                        </Button>
                    </div>
                    {saved.length === 0 ? (
                        <p className="text-xs text-muted-foreground font-mono text-center py-6">No saved strategies yet</p>
                    ) : (
                        <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                            {saved.map((s) => (
                                <div key={s.name} className="flex items-center gap-2 p-2.5 rounded-lg border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-colors">
                                    <button onClick={() => onApply(s.strategy)} className="flex-1 text-left">
                                        <span className="text-sm font-mono font-semibold text-foreground block">{s.name}</span>
                                        <span className="text-[10px] text-muted-foreground font-mono">{new Date(s.savedAt).toLocaleDateString()}</span>
                                    </button>
                                    <button onClick={() => handleDelete(s.name)} className="text-muted-foreground hover:text-red-400 p-1">
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </TabsContent>
            </Tabs>
        </div>
    );
}

// ─── Ticker Input ─────────────────────────────────────────────────────────────

function TickerInput({ tickers, onChange }) {
    const [input, setInput] = useState('');

    const addTicker = () => {
        const t = input.trim().toUpperCase();
        if (t && !tickers.includes(t)) onChange([...tickers, t]);
        setInput('');
    };

    return (
        <div>
            <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Universe</label>
            <div className="flex flex-wrap gap-1.5 mt-1 mb-2">
                {tickers.map((t) => (
                    <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-primary/15 text-primary text-xs font-mono">
                        {t}
                        <button onClick={() => onChange(tickers.filter((x) => x !== t))} className="hover:text-red-400"><X className="w-3 h-3" /></button>
                    </span>
                ))}
            </div>
            <div className="flex gap-2">
                <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTicker())}
                    placeholder="Add ticker..."
                    className="flex-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <Button size="sm" variant="outline" onClick={addTicker} className="text-xs font-mono"><Plus className="w-3 h-3" /></Button>
            </div>
        </div>
    );
}

// ─── Indicator Editor ─────────────────────────────────────────────────────────

function IndicatorEditor({ indicators, onChange }) {
    const entries = Object.entries(indicators);

    const addIndicator = () => {
        const name = `ind_${entries.length + 1}`;
        onChange({ ...indicators, [name]: { type: 'sma', period: 20 } });
    };

    const removeIndicator = (name) => {
        const next = { ...indicators };
        delete next[name];
        onChange(next);
    };

    const updateIndicator = (name, field, value) => {
        onChange({ ...indicators, [name]: { ...indicators[name], [field]: value } });
    };

    const renameIndicator = (oldName, newName) => {
        if (newName === oldName || !newName.trim()) return;
        const next = {};
        for (const [k, v] of Object.entries(indicators)) {
            next[k === oldName ? newName.trim() : k] = v;
        }
        onChange(next);
    };

    return (
        <div>
            <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Indicators</label>
                <Button size="sm" variant="ghost" onClick={addIndicator} className="text-xs font-mono text-primary h-6"><Plus className="w-3 h-3 mr-1" />Add</Button>
            </div>
            <div className="space-y-2">
                {entries.map(([name, spec]) => {
                    const typeDef = INDICATOR_TYPES.find((t) => t.value === spec.type);
                    return (
                        <div key={name} className="flex items-center gap-2 p-2 rounded bg-white/[0.03] border border-white/5">
                            <input value={name} onChange={(e) => renameIndicator(name, e.target.value)}
                                className="w-24 px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-primary" />
                            <select value={spec.type} onChange={(e) => updateIndicator(name, 'type', e.target.value)}
                                className="px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground focus:outline-none">
                                {INDICATOR_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                            </select>
                            {typeDef?.params.filter((p) => p !== 'source').map((p) => (
                                <input key={p} type="number" placeholder={p} value={spec[p] ?? ''}
                                    onChange={(e) => updateIndicator(name, p, e.target.value ? Number(e.target.value) : undefined)}
                                    className="w-16 px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground placeholder:text-muted-foreground focus:outline-none" />
                            ))}
                            <button onClick={() => removeIndicator(name)} className="text-muted-foreground hover:text-red-400 ml-auto"><X className="w-3.5 h-3.5" /></button>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ─── Condition Editor ─────────────────────────────────────────────────────────

function ConditionEditor({ label, conditions, combinator, onChange, isExit }) {
    const addCondition = () => {
        onChange({ [combinator]: [...conditions, { gt: ['close', 0] }] });
    };

    const removeCondition = (idx) => {
        onChange({ [combinator]: conditions.filter((_, i) => i !== idx) });
    };

    const updateCondition = (idx, cond) => {
        const next = [...conditions];
        next[idx] = cond;
        onChange({ [combinator]: next });
    };

    return (
        <div>
            <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">{label}</label>
                <div className="flex items-center gap-2">
                    <select value={combinator} onChange={(e) => onChange({ [e.target.value]: conditions })}
                        className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground">
                        <option value="all">ALL (AND)</option>
                        <option value="any">ANY (OR)</option>
                    </select>
                    <Button size="sm" variant="ghost" onClick={addCondition} className="text-xs font-mono text-primary h-6"><Plus className="w-3 h-3 mr-1" />Add</Button>
                </div>
            </div>
            <div className="space-y-2">
                {conditions.map((cond, idx) => {
                    const op = Object.keys(cond)[0];
                    const val = cond[op];
                    const isTradePred = ['hold_days_gte', 'profit_pct_gte', 'loss_pct_gte'].includes(op);

                    if (isTradePred) {
                        return (
                            <div key={idx} className="flex items-center gap-2 p-2 rounded bg-white/[0.03] border border-white/5">
                                <select value={op} onChange={(e) => {
                                    const newOp = e.target.value;
                                    updateCondition(idx, ['hold_days_gte','profit_pct_gte','loss_pct_gte'].includes(newOp) ? { [newOp]: val } : { [newOp]: ['close', 0] });
                                }} className="px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground">
                                    {COMPARATORS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                                    {isExit && <><option value="hold_days_gte">Hold Days &gt;=</option><option value="profit_pct_gte">Profit % &gt;=</option><option value="loss_pct_gte">Loss % &gt;=</option></>}
                                </select>
                                <input type="number" value={val} onChange={(e) => updateCondition(idx, { [op]: Number(e.target.value) || 0 })}
                                    className="w-20 px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground" />
                                <button onClick={() => removeCondition(idx)} className="text-muted-foreground hover:text-red-400 ml-auto"><X className="w-3.5 h-3.5" /></button>
                            </div>
                        );
                    }

                    return (
                        <div key={idx} className="flex items-center gap-2 p-2 rounded bg-white/[0.03] border border-white/5">
                            <input value={Array.isArray(val) ? val[0] : ''} onChange={(e) => updateCondition(idx, { [op]: [e.target.value, Array.isArray(val) ? val[1] : 0] })}
                                placeholder="lhs" className="w-24 px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground placeholder:text-muted-foreground" />
                            <select value={op} onChange={(e) => {
                                const newOp = e.target.value;
                                updateCondition(idx, ['hold_days_gte','profit_pct_gte','loss_pct_gte'].includes(newOp) ? { [newOp]: 20 } : { [newOp]: val });
                            }} className="px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground">
                                {COMPARATORS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                                {isExit && <><option value="hold_days_gte">Hold Days &gt;=</option><option value="profit_pct_gte">Profit % &gt;=</option><option value="loss_pct_gte">Loss % &gt;=</option></>}
                            </select>
                            <input value={Array.isArray(val) ? val[1] : ''} onChange={(e) => {
                                const v = e.target.value;
                                const parsed = isNaN(Number(v)) ? v : Number(v);
                                updateCondition(idx, { [op]: [Array.isArray(val) ? val[0] : '', parsed] });
                            }} placeholder="rhs" className="w-24 px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground placeholder:text-muted-foreground" />
                            <button onClick={() => removeCondition(idx)} className="text-muted-foreground hover:text-red-400 ml-auto"><X className="w-3.5 h-3.5" /></button>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ─── Metric Card with Tooltip ─────────────────────────────────────────────────

function MetricCard({ label, value, icon: Icon, color = 'text-primary', tip }) {
    return (
        <TooltipProvider delayDuration={200}>
            <Tooltip>
                <TooltipTrigger asChild>
                    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3 hover:bg-white/[0.04] transition-colors cursor-default">
                        <div className="flex items-center gap-2 mb-1">
                            {Icon && <Icon className={`w-3.5 h-3.5 ${color}`} />}
                            <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider leading-none">{label}</span>
                        </div>
                        <p className={`text-lg font-bold font-mono ${color} leading-tight`}>{value}</p>
                    </div>
                </TooltipTrigger>
                {tip && <TooltipContent side="top" className="max-w-xs text-xs font-mono">{tip}</TooltipContent>}
            </Tooltip>
        </TooltipProvider>
    );
}

// ─── Metrics Grid ─────────────────────────────────────────────────────────────

function MetricsGrid({ metrics, trades }) {
    const derived = useMemo(() => deriveMetrics(metrics, trades), [metrics, trades]);

    return (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-2.5">
            {METRIC_DEFS.map(def => (
                <MetricCard
                    key={def.key}
                    label={def.label}
                    value={fmt(derived[def.key], def.type)}
                    icon={def.icon}
                    color={metricColor(def, derived[def.key])}
                    tip={def.tip}
                />
            ))}
        </div>
    );
}

// ─── Monthly Returns Heatmap ──────────────────────────────────────────────────

function MonthlyHeatmap({ monthlyReturns }) {
    const [hoveredCell, setHoveredCell] = useState(null);

    const parsed = useMemo(() => {
        if (!monthlyReturns || typeof monthlyReturns !== 'object') return null;
        const years = {};
        for (const [key, val] of Object.entries(monthlyReturns)) {
            const parts = key.split('-');
            if (parts.length < 2) continue;
            const year = parts[0];
            const month = parseInt(parts[1], 10) - 1;
            if (!years[year]) years[year] = {};
            years[year][month] = val;
        }
        return years;
    }, [monthlyReturns]);

    if (!parsed || Object.keys(parsed).length === 0) return null;

    const allVals = Object.values(parsed).flatMap(y => Object.values(y));
    const absMax = Math.max(Math.abs(Math.min(...allVals)), Math.abs(Math.max(...allVals)), 0.01);

    const cellStyle = (val) => {
        if (val == null) return { backgroundColor: 'rgba(255,255,255,0.02)' };
        const intensity = Math.min(Math.abs(val) / absMax, 1);
        if (val > 0) {
            const alpha = 0.1 + intensity * 0.55;
            return { backgroundColor: `rgba(34,197,94,${alpha})` };
        }
        const alpha = 0.1 + intensity * 0.55;
        return { backgroundColor: `rgba(239,68,68,${alpha})` };
    };

    const sortedYears = Object.keys(parsed).sort();

    return (
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
            <h3 className="text-sm font-mono font-semibold text-foreground mb-4 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-primary" />
                Monthly Returns
            </h3>
            <div className="overflow-x-auto">
                <div className="inline-block min-w-full">
                    <div className="grid gap-px" style={{ gridTemplateColumns: `64px repeat(12, minmax(48px, 1fr)) 64px` }}>
                        {/* Header row */}
                        <div className="text-[10px] font-mono text-muted-foreground p-1.5 text-center" />
                        {MONTH_LABELS.map(m => (
                            <div key={m} className="text-[10px] font-mono text-muted-foreground p-1.5 text-center font-semibold">{m}</div>
                        ))}
                        <div className="text-[10px] font-mono text-muted-foreground p-1.5 text-center font-semibold">Year</div>

                        {sortedYears.map(year => {
                            const yearData = parsed[year];
                            const yearVals = Object.values(yearData);
                            const yearTotal = yearVals.reduce((a, b) => a + b, 0);
                            return [
                                <div key={`${year}-label`} className="text-xs font-mono text-muted-foreground p-1.5 flex items-center justify-center font-semibold">
                                    {year}
                                </div>,
                                ...Array.from({ length: 12 }, (_, m) => {
                                    const val = yearData[m];
                                    const cellKey = `${year}-${m}`;
                                    return (
                                        <div
                                            key={cellKey}
                                            className="relative rounded-sm p-1.5 text-center cursor-default transition-all hover:ring-1 hover:ring-white/30"
                                            style={cellStyle(val)}
                                            onMouseEnter={() => setHoveredCell(cellKey)}
                                            onMouseLeave={() => setHoveredCell(null)}
                                        >
                                            <span className={`text-[11px] font-mono font-semibold ${val == null ? 'text-white/10' : val >= 0 ? 'text-white' : 'text-white'}`}>
                                                {val != null ? `${(val * 100).toFixed(1)}%` : ''}
                                            </span>
                                            {hoveredCell === cellKey && val != null && (
                                                <div className="absolute z-20 bottom-full left-1/2 -translate-x-1/2 mb-2 px-2.5 py-1.5 rounded bg-card border border-white/20 shadow-xl whitespace-nowrap">
                                                    <div className="text-[10px] font-mono text-muted-foreground">{MONTH_LABELS[m]} {year}</div>
                                                    <div className={`text-xs font-mono font-bold ${val >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                        {(val * 100).toFixed(2)}%
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    );
                                }),
                                <div key={`${year}-total`} className="rounded-sm p-1.5 text-center" style={cellStyle(yearTotal)}>
                                    <span className="text-[11px] font-mono font-bold text-white">
                                        {(yearTotal * 100).toFixed(1)}%
                                    </span>
                                </div>
                            ];
                        })}
                    </div>
                </div>
            </div>
            <div className="flex items-center justify-center gap-4 mt-3 text-[10px] font-mono text-muted-foreground">
                <div className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'rgba(239,68,68,0.5)' }} />Loss
                </div>
                <div className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded-sm bg-white/[0.04]" />Flat
                </div>
                <div className="flex items-center gap-1.5">
                    <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'rgba(34,197,94,0.5)' }} />Gain
                </div>
            </div>
        </div>
    );
}

// ─── Equity Curve with Benchmark ──────────────────────────────────────────────

function EquityCurveChart({ equityCurve, startDate, endDate, capital, showBenchmarkToggle = true, title = 'Equity Curve' }) {
    const [showBenchmark, setShowBenchmark] = useState(false);
    const [benchmarkData, setBenchmarkData] = useState(null);
    const [benchLoading, setBenchLoading] = useState(false);

    useEffect(() => {
        if (!showBenchmark || benchmarkData) return;
        setBenchLoading(true);
        fetchBenchmark({ ticker: 'SPY', start: startDate, end: endDate, initial_capital: capital })
            .then(setBenchmarkData)
            .catch(() => toast.error('Failed to fetch benchmark'))
            .finally(() => setBenchLoading(false));
    }, [showBenchmark, benchmarkData, startDate, endDate, capital]);

    const merged = useMemo(() => {
        if (!equityCurve?.length) return [];
        if (!showBenchmark || !benchmarkData?.equity_curve?.length) {
            return equityCurve.map(d => ({ date: d.date, equity: d.equity }));
        }
        const benchMap = {};
        benchmarkData.equity_curve.forEach(d => { benchMap[d.date] = d.equity; });
        return equityCurve.map(d => ({
            date: d.date,
            equity: d.equity,
            benchmark: benchMap[d.date] ?? null,
        }));
    }, [equityCurve, showBenchmark, benchmarkData]);

    if (!equityCurve?.length) return null;

    return (
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-mono font-semibold text-foreground flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-primary" />
                    {title}
                </h3>
                {showBenchmarkToggle && (
                    <Button
                        size="sm" variant="ghost"
                        onClick={() => setShowBenchmark(!showBenchmark)}
                        className="text-xs font-mono gap-1.5 h-7"
                    >
                        {benchLoading ? <Loader2 className="w-3 h-3 animate-spin" /> :
                            showBenchmark ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                        {showBenchmark ? 'Hide' : 'Show'} SPY
                    </Button>
                )}
            </div>
            <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={merged}>
                    <defs>
                        <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fontFamily: 'monospace', fill: 'hsl(var(--muted-foreground))' }}
                        tickFormatter={(d) => d?.slice(0, 10)} interval="preserveStartEnd" minTickGap={80} />
                    <YAxis tick={{ fontSize: 10, fontFamily: 'monospace', fill: 'hsl(var(--muted-foreground))' }}
                        tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} width={60} />
                    <RechartsTooltip
                        contentStyle={{ background: 'hsl(var(--card))', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontFamily: 'monospace', fontSize: '12px' }}
                        formatter={(v, name) => [`$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, name === 'benchmark' ? 'SPY B&H' : 'Strategy']}
                        labelFormatter={(d) => d?.slice(0, 10)}
                    />
                    <Area type="monotone" dataKey="equity" stroke="hsl(var(--primary))" fill="url(#eqGrad)" strokeWidth={2} dot={false} name="Strategy" />
                    {showBenchmark && (
                        <Area type="monotone" dataKey="benchmark" stroke="#6366f1" fill="none" strokeWidth={1.5} strokeDasharray="6 3" dot={false} name="SPY B&H" />
                    )}
                    {showBenchmark && <Legend wrapperStyle={{ fontFamily: 'monospace', fontSize: '11px' }} />}
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
}

// ─── AI Narrative Card ────────────────────────────────────────────────────────

function AiNarrativeCard({ strategy, metrics, trades }) {
    const [critique, setCritique] = useState(null);
    const [loading, setLoading] = useState(false);
    const [expanded, setExpanded] = useState({});

    const fetchCritique = useCallback(async () => {
        setLoading(true);
        try {
            const tradesSummary = {
                count: trades?.length || 0,
                winners: trades?.filter(t => t.pnl > 0).length || 0,
                losers: trades?.filter(t => t.pnl <= 0).length || 0,
                avg_pnl: trades?.length ? (trades.reduce((s, t) => s + (t.pnl || 0), 0) / trades.length) : 0,
            };
            const res = await aiCritique({ strategy, metrics, trades_summary: tradesSummary });
            setCritique(res);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'AI critique failed');
        } finally {
            setLoading(false);
        }
    }, [strategy, metrics, trades]);

    const toggleSection = (section) => setExpanded(prev => ({ ...prev, [section]: !prev[section] }));

    const confScore = critique?.confidence_score || 0;
    const confColor = confScore >= 7 ? 'text-green-400' : confScore >= 4 ? 'text-amber-400' : 'text-red-400';

    return (
        <div className="rounded-xl border border-white/10 bg-gradient-to-br from-primary/5 via-transparent to-transparent p-5">
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <Brain className="w-4 h-4 text-primary" />
                    <span className="text-sm font-mono font-semibold text-foreground">AI Analyst Summary</span>
                </div>
                <Button size="sm" variant={critique ? 'ghost' : 'default'} onClick={fetchCritique} disabled={loading} className="text-xs font-mono gap-1.5 h-7">
                    {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : critique ? <RefreshCw className="w-3 h-3" /> : <Sparkles className="w-3 h-3" />}
                    {critique ? 'Regenerate' : 'Run AI Analysis'}
                </Button>
            </div>

            {!critique && !loading && (
                <p className="text-xs font-mono text-muted-foreground text-center py-4">Click "Run AI Analysis" to get a professional quant analyst review of your strategy</p>
            )}

            {loading && !critique && (
                <div className="flex items-center gap-2 py-6 justify-center">
                    <Loader2 className="w-4 h-4 animate-spin text-primary" />
                    <span className="text-xs font-mono text-muted-foreground">Analyzing strategy…</span>
                </div>
            )}

            {critique && (
                <div className="space-y-4">
                    <p className="text-sm text-foreground/90 leading-relaxed font-mono">{critique.narrative}</p>

                    <div className="flex items-center gap-3">
                        <span className="text-xs font-mono text-muted-foreground">Confidence</span>
                        <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
                            <div className={`h-full rounded-full transition-all duration-700 ${confScore >= 7 ? 'bg-green-500' : confScore >= 4 ? 'bg-amber-500' : 'bg-red-500'}`}
                                style={{ width: `${confScore * 10}%` }} />
                        </div>
                        <span className={`text-sm font-mono font-bold ${confColor}`}>{confScore}/10</span>
                    </div>

                    {[
                        { key: 'strengths', label: 'Strengths', icon: TrendingUp, iconColor: 'text-green-400' },
                        { key: 'weaknesses', label: 'Weaknesses', icon: AlertTriangle, iconColor: 'text-red-400' },
                        { key: 'suggestions', label: 'Suggestions', icon: Lightbulb, iconColor: 'text-amber-400' },
                    ].map(({ key, label, icon: SIcon, iconColor }) => (
                        critique[key]?.length > 0 && (
                            <div key={key}>
                                <button onClick={() => toggleSection(key)} className="flex items-center gap-2 w-full text-left group">
                                    <SIcon className={`w-3.5 h-3.5 ${iconColor}`} />
                                    <span className="text-xs font-mono font-semibold text-foreground uppercase tracking-wider flex-1">{label}</span>
                                    {expanded[key] ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
                                </button>
                                {expanded[key] && (
                                    <ul className="mt-2 space-y-1 pl-5">
                                        {critique[key].map((item, i) => (
                                            <li key={i} className="text-xs font-mono text-muted-foreground leading-relaxed list-disc">{item}</li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        )
                    ))}
                </div>
            )}
        </div>
    );
}

// ─── Trade Log ────────────────────────────────────────────────────────────────

function TradeLog({ trades }) {
    const [page, setPage] = useState(0);
    const [sortKey, setSortKey] = useState(null);
    const [sortDir, setSortDir] = useState('asc');
    const perPage = 25;

    const sorted = useMemo(() => {
        if (!trades?.length) return [];
        if (!sortKey) return trades;
        const arr = [...trades];
        arr.sort((a, b) => {
            let va = a[sortKey], vb = b[sortKey];
            if (typeof va === 'string') va = va?.toLowerCase();
            if (typeof vb === 'string') vb = vb?.toLowerCase();
            if (va < vb) return sortDir === 'asc' ? -1 : 1;
            if (va > vb) return sortDir === 'asc' ? 1 : -1;
            return 0;
        });
        return arr;
    }, [trades, sortKey, sortDir]);

    const paginated = useMemo(() => sorted.slice(page * perPage, (page + 1) * perPage), [sorted, page]);
    const totalPages = Math.ceil((sorted.length || 1) / perPage);

    const handleSort = (key) => {
        if (sortKey === key) {
            setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        } else {
            setSortKey(key);
            setSortDir('asc');
        }
        setPage(0);
    };

    if (!trades?.length) return null;

    const columns = [
        { key: 'symbol', label: 'Symbol', align: 'left' },
        { key: 'entry_date', label: 'Entry', align: 'left' },
        { key: 'exit_date', label: 'Exit', align: 'left' },
        { key: 'entry_price', label: 'Entry $', align: 'right' },
        { key: 'exit_price', label: 'Exit $', align: 'right' },
        { key: 'shares', label: 'Shares', align: 'right' },
        { key: 'pnl', label: 'P&L', align: 'right' },
        { key: 'return_pct', label: 'Return', align: 'right' },
        { key: 'bars_held', label: 'Bars', align: 'right' },
        { key: 'exit_reason', label: 'Reason', align: 'left' },
    ];

    return (
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-mono font-semibold text-foreground flex items-center gap-2">
                    <FileText className="w-4 h-4 text-primary" />
                    Trade Log ({trades.length})
                </h3>
                <Button size="sm" variant="outline" onClick={() => exportTradesCsv(trades)} className="text-xs font-mono gap-1 h-7">
                    <Download className="w-3 h-3" />CSV
                </Button>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono">
                    <thead>
                        <tr className="text-muted-foreground border-b border-white/10">
                            {columns.map(col => (
                                <th key={col.key} className={`text-${col.align} py-2 px-2 cursor-pointer hover:text-foreground transition-colors select-none`}
                                    onClick={() => handleSort(col.key)}>
                                    <span className="inline-flex items-center gap-1">
                                        {col.label}
                                        {sortKey === col.key && <ArrowUpDown className="w-2.5 h-2.5" />}
                                    </span>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {paginated.map((t, i) => (
                            <tr key={i} className={`border-b border-white/5 transition-colors ${t.pnl >= 0 ? 'hover:bg-green-500/[0.04] bg-green-500/[0.02]' : 'hover:bg-red-500/[0.04] bg-red-500/[0.02]'}`}>
                                <td className="py-1.5 px-2 text-primary font-semibold">{t.symbol}</td>
                                <td className="py-1.5 px-2">{t.entry_date?.slice(0, 10)}</td>
                                <td className="py-1.5 px-2">{t.exit_date?.slice(0, 10)}</td>
                                <td className="py-1.5 px-2 text-right">{fmt(t.entry_price, 'money')}</td>
                                <td className="py-1.5 px-2 text-right">{fmt(t.exit_price, 'money')}</td>
                                <td className="py-1.5 px-2 text-right">{Math.round(t.shares)}</td>
                                <td className={`py-1.5 px-2 text-right font-semibold ${t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmt(t.pnl, 'money')}</td>
                                <td className={`py-1.5 px-2 text-right ${t.return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmt(t.return_pct)}</td>
                                <td className="py-1.5 px-2 text-right">{t.bars_held}</td>
                                <td className="py-1.5 px-2 text-muted-foreground">{t.exit_reason}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {totalPages > 1 && (
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/5">
                    <span className="text-[10px] font-mono text-muted-foreground">
                        {page * perPage + 1}–{Math.min((page + 1) * perPage, sorted.length)} of {sorted.length}
                    </span>
                    <div className="flex items-center gap-1">
                        <Button size="sm" variant="ghost" disabled={page === 0} onClick={() => setPage(p => p - 1)} className="h-7 w-7 p-0">
                            <ChevronLeft className="w-3.5 h-3.5" />
                        </Button>
                        <span className="text-xs font-mono text-muted-foreground px-2">{page + 1}/{totalPages}</span>
                        <Button size="sm" variant="ghost" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)} className="h-7 w-7 p-0">
                            <ChevronRight className="w-3.5 h-3.5" />
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}

// ─── Walk-Forward Panel ───────────────────────────────────────────────────────

function WalkForwardPanel({ walkForward }) {
    if (!walkForward) return (
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-12 text-center">
            <Layers className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-sm font-mono text-muted-foreground">Run a Walk-Forward analysis to see results here</p>
        </div>
    );

    const folds = walkForward.folds || [];
    const oosMetrics = walkForward.aggregate_oos?.metrics;
    const oosEquity = walkForward.aggregate_oos?.equity_curve;

    const positiveFolds = folds.filter(f => (f.test?.metrics?.total_return ?? 0) > 0).length;
    const consistency = folds.length ? ((positiveFolds / folds.length) * 100).toFixed(0) : '—';

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <MetricCard label="Windows" value={walkForward.windows?.length || folds.length} icon={Layers} color="text-primary" tip="Number of walk-forward windows" />
                <MetricCard label="OOS Return" value={fmt(oosMetrics?.total_return)} icon={TrendingUp}
                    color={oosMetrics?.total_return >= 0 ? 'text-green-400' : 'text-red-400'} tip="Aggregate out-of-sample return" />
                <MetricCard label="OOS Sharpe" value={fmt(oosMetrics?.sharpe, 'ratio')} icon={BarChart3} tip="Aggregate out-of-sample Sharpe ratio" />
                <MetricCard label="Consistency" value={`${consistency}%`} icon={Target}
                    color={Number(consistency) >= 60 ? 'text-green-400' : 'text-amber-400'} tip="Percentage of folds with positive OOS return" />
            </div>

            {oosEquity?.length > 0 && (
                <EquityCurveChart equityCurve={oosEquity} showBenchmarkToggle={false} title="Out-of-Sample Equity Curve" />
            )}

            {folds.length > 0 && (
                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
                    <h3 className="text-sm font-mono font-semibold text-foreground mb-3">Walk-Forward Folds</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-xs font-mono">
                            <thead>
                                <tr className="text-muted-foreground border-b border-white/10">
                                    <th className="text-left py-2 px-2">#</th>
                                    <th className="text-left py-2 px-2">Train Period</th>
                                    <th className="text-left py-2 px-2">Test Period</th>
                                    <th className="text-right py-2 px-2">IS Return</th>
                                    <th className="text-right py-2 px-2">OOS Return</th>
                                    <th className="text-right py-2 px-2">OOS Sharpe</th>
                                </tr>
                            </thead>
                            <tbody>
                                {folds.map((w, i) => (
                                    <tr key={i} className="border-b border-white/5 hover:bg-white/[0.02]">
                                        <td className="py-2 px-2 text-muted-foreground">{i + 1}</td>
                                        <td className="py-2 px-2">{w.window.train_start} → {w.window.train_end}</td>
                                        <td className="py-2 px-2">{w.window.test_start} → {w.window.test_end}</td>
                                        <td className="py-2 px-2 text-right">{fmt(w.train?.metrics?.total_return)}</td>
                                        <td className={`py-2 px-2 text-right ${(w.test?.metrics?.total_return ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {fmt(w.test?.metrics?.total_return)}
                                        </td>
                                        <td className="py-2 px-2 text-right">{fmt(w.test?.metrics?.sharpe, 'ratio')}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}

// ─── Monte Carlo Panel ────────────────────────────────────────────────────────

function MonteCarloPanel({ trades, capital }) {
    const [mcData, setMcData] = useState(null);
    const [loading, setLoading] = useState(false);

    const runSim = useCallback(async () => {
        if (!trades?.length) {
            toast.error('Run a backtest first to generate trades');
            return;
        }
        setLoading(true);
        try {
            const res = await runMonteCarlo({ trades, initial_capital: capital, num_simulations: 500 });
            const p5 = res.percentile_5 || [];
            const p50 = res.percentile_50 || [];
            const p95 = res.percentile_95 || [];
            const curves = p50.map((_, i) => ({
                trade_num: i,
                p5: p5[i] || 0,
                p50: p50[i] || 0,
                p95: p95[i] || 0,
            }));
            setMcData({
                percentile_5: p5[p5.length - 1] || capital,
                percentile_50: p50[p50.length - 1] || capital,
                percentile_95: p95[p95.length - 1] || capital,
                win_pct: res.win_pct,
                percentile_curves: curves,
            });
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Monte Carlo simulation failed');
        } finally {
            setLoading(false);
        }
    }, [trades, capital]);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-mono font-semibold text-foreground flex items-center gap-2">
                    <Activity className="w-4 h-4 text-primary" />
                    Monte Carlo Simulation
                </h3>
                <Button size="sm" onClick={runSim} disabled={loading || !trades?.length} className="text-xs font-mono gap-1.5">
                    {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                    Run 500 Simulations
                </Button>
            </div>

            {!mcData && !loading && (
                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-12 text-center">
                    <Activity className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
                    <p className="text-sm font-mono text-muted-foreground">Shuffles the order of your trades 500 times to see the range of possible outcomes</p>
                </div>
            )}

            {loading && (
                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-12 text-center">
                    <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-3" />
                    <p className="text-sm font-mono text-muted-foreground">Running 500 simulations…</p>
                </div>
            )}

            {mcData && (
                <>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <MetricCard label="5th Percentile" value={fmt(mcData.percentile_5, 'money')} icon={TrendingDown}
                            color="text-red-400" tip="Worst-case scenario (5th percentile)" />
                        <MetricCard label="Median" value={fmt(mcData.percentile_50, 'money')} icon={BarChart3}
                            color="text-foreground" tip="Median outcome across all simulations" />
                        <MetricCard label="95th Percentile" value={fmt(mcData.percentile_95, 'money')} icon={TrendingUp}
                            color="text-green-400" tip="Best-case scenario (95th percentile)" />
                        <MetricCard label="Win Probability" value={fmt(mcData.win_pct)} icon={Target}
                            color={mcData.win_pct >= 0.5 ? 'text-green-400' : 'text-red-400'} tip="Probability of ending with profit" />
                    </div>

                    {mcData.percentile_curves && (
                        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
                            <h3 className="text-sm font-mono font-semibold text-foreground mb-4">Percentile Equity Curves</h3>
                            <ResponsiveContainer width="100%" height={300}>
                                <LineChart data={mcData.percentile_curves}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                    <XAxis dataKey="trade_num" tick={{ fontSize: 10, fontFamily: 'monospace', fill: 'hsl(var(--muted-foreground))' }} label={{ value: 'Trade #', position: 'insideBottom', offset: -5, fontSize: 10, fontFamily: 'monospace', fill: 'hsl(var(--muted-foreground))' }} />
                                    <YAxis tick={{ fontSize: 10, fontFamily: 'monospace', fill: 'hsl(var(--muted-foreground))' }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} width={60} />
                                    <RechartsTooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontFamily: 'monospace', fontSize: '12px' }} />
                                    <Line type="monotone" dataKey="p5" stroke="#ef4444" strokeWidth={1.5} dot={false} name="5th %ile" />
                                    <Line type="monotone" dataKey="p50" stroke="#f59e0b" strokeWidth={2} dot={false} name="Median" />
                                    <Line type="monotone" dataKey="p95" stroke="#22c55e" strokeWidth={1.5} dot={false} name="95th %ile" />
                                    <Legend wrapperStyle={{ fontFamily: 'monospace', fontSize: '11px' }} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

// ─── Risk Analytics Panel ─────────────────────────────────────────────────────

function RiskAnalyticsPanel({ metrics, trades }) {
    const derived = useMemo(() => deriveMetrics(metrics, trades), [metrics, trades]);

    const winStreak = useMemo(() => {
        if (!trades?.length) return { max_win: 0, max_loss: 0, current: 0 };
        let maxWin = 0, maxLoss = 0, curWin = 0, curLoss = 0;
        for (const t of trades) {
            if (t.pnl >= 0) { curWin++; curLoss = 0; maxWin = Math.max(maxWin, curWin); }
            else { curLoss++; curWin = 0; maxLoss = Math.max(maxLoss, curLoss); }
        }
        return { max_win: maxWin, max_loss: maxLoss };
    }, [trades]);

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                <MetricCard label="Max Drawdown" value={fmt(derived.max_drawdown)} icon={TrendingDown} color="text-red-400" tip="Largest peak-to-trough decline" />
                <MetricCard label="Volatility" value={fmt(derived.volatility)} icon={AlertTriangle} color="text-amber-400" tip="Annualized standard deviation of returns" />
                <MetricCard label="Calmar Ratio" value={fmt(derived.calmar, 'ratio')} icon={Shield}
                    color={derived.calmar >= 1 ? 'text-green-400' : 'text-red-400'} tip="CAGR / Max Drawdown" />
                <MetricCard label="Sortino Ratio" value={fmt(derived.sortino, 'ratio')} icon={BarChart3} tip="Return / downside deviation" />
                <MetricCard label="Best Streak" value={`${winStreak.max_win} wins`} icon={TrendingUp} color="text-green-400" tip="Longest consecutive winning streak" />
                <MetricCard label="Worst Streak" value={`${winStreak.max_loss} losses`} icon={TrendingDown} color="text-red-400" tip="Longest consecutive losing streak" />
                <MetricCard label="Num Trades" value={fmt(derived.num_trades, 'int')} icon={Layers} tip="Total number of completed trades" />
                <MetricCard label="Avg P&L" value={fmt(derived.avg_trade_pnl, 'money')} icon={BarChart3}
                    color={derived.avg_trade_pnl >= 0 ? 'text-green-400' : 'text-red-400'} tip="Average profit/loss per trade" />
            </div>

            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-6 text-center">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    {[
                        { label: 'Value at Risk (95%)', value: 'Coming soon', color: 'text-muted-foreground' },
                        { label: 'CVaR (95%)', value: 'Coming soon', color: 'text-muted-foreground' },
                        { label: 'Beta vs SPY', value: 'Coming soon', color: 'text-muted-foreground' },
                        { label: 'Skewness', value: 'Coming soon', color: 'text-muted-foreground' },
                    ].map(item => (
                        <div key={item.label} className="p-3 rounded-lg bg-white/[0.02] border border-white/5">
                            <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider block mb-1">{item.label}</span>
                            <span className={`text-sm font-mono ${item.color} italic`}>{item.value}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

// ─── Python Code Modal ────────────────────────────────────────────────────────

function PythonCodeModal({ open, onClose, strategy, startDate, endDate, capital }) {
    const [copied, setCopied] = useState(false);
    const code = useMemo(() => generatePythonCode(strategy, startDate, endDate, capital), [strategy, startDate, endDate, capital]);

    const handleCopy = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <Dialog open={open} onOpenChange={onClose}>
            <DialogContent className="max-w-2xl max-h-[80vh] bg-card border-white/10">
                <DialogHeader>
                    <DialogTitle className="font-mono flex items-center gap-2">
                        <Terminal className="w-5 h-5 text-primary" />
                        Backtrader Python Script
                    </DialogTitle>
                    <DialogDescription className="font-mono text-xs">
                        Auto-generated script — edit the entry/exit logic to match your conditions
                    </DialogDescription>
                </DialogHeader>
                <div className="relative">
                    <Button size="sm" variant="outline" onClick={handleCopy}
                        className="absolute top-2 right-2 z-10 text-xs font-mono gap-1 h-7">
                        {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                        {copied ? 'Copied' : 'Copy'}
                    </Button>
                    <pre className="text-xs font-mono text-green-400/90 bg-black/40 rounded-lg p-4 overflow-auto max-h-[50vh] border border-white/5">
                        {code}
                    </pre>
                </div>
            </DialogContent>
        </Dialog>
    );
}

// ─── Loading Overlay ──────────────────────────────────────────────────────────

function LoadingOverlay({ stage }) {
    return (
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-12 text-center">
            <Loader2 className="w-12 h-12 text-primary mx-auto mb-4 animate-spin" />
            <h3 className="text-lg font-semibold text-foreground mb-4 font-mono">Running Backtest</h3>
            <div className="space-y-2 max-w-xs mx-auto">
                {LOADING_STAGES.map((s, i) => (
                    <div key={i} className={`flex items-center gap-2 text-xs font-mono transition-all duration-300 ${i <= stage ? 'text-foreground' : 'text-muted-foreground/40'}`}>
                        {i < stage ? <Check className="w-3.5 h-3.5 text-green-400" /> :
                            i === stage ? <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" /> :
                                <div className="w-3.5 h-3.5 rounded-full border border-white/20" />}
                        {s}
                    </div>
                ))}
            </div>
        </div>
    );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Backtest() {
    const [strategy, setStrategy] = useState(defaultStrategy);
    const [startDate, setStartDate] = useState('2020-01-01');
    const [endDate, setEndDate] = useState(new Date().toISOString().slice(0, 10));
    const [capital, setCapital] = useState(100000);
    const [loading, setLoading] = useState(false);
    const [loadingStage, setLoadingStage] = useState(0);
    const [result, setResult] = useState(null);
    const [walkForward, setWalkForward] = useState(null);
    const [showJson, setShowJson] = useState(false);
    const [jsonText, setJsonText] = useState('');
    const [wfTrainMonths, setWfTrainMonths] = useState(36);
    const [wfTestMonths, setWfTestMonths] = useState(12);
    const [resultTab, setResultTab] = useState('results');
    const [showPython, setShowPython] = useState(false);
    const loadingIntervalRef = useRef(null);

    const entryCombinator = Object.keys(strategy.entry)[0] || 'all';
    const entryConditions = strategy.entry[entryCombinator] || [];
    const exitCombinator = Object.keys(strategy.exit)[0] || 'any';
    const exitConditions = strategy.exit[exitCombinator] || [];

    // Read shared strategy from URL on mount
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const encoded = params.get('strategy');
        if (encoded) {
            const decoded = decodeStrategyUrl(encoded);
            if (decoded?.strategy) {
                setStrategy(decoded.strategy);
                if (decoded.start) setStartDate(decoded.start);
                if (decoded.end) setEndDate(decoded.end);
                toast.success('Strategy loaded from shared link');
                window.history.replaceState({}, '', window.location.pathname);
            }
        }
    }, []);

    // Keyboard shortcut: Cmd+Enter / Ctrl+Enter to run
    useEffect(() => {
        const handler = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                if (!loading) handleRun();
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    });

    const startLoadingAnimation = () => {
        setLoadingStage(0);
        let stage = 0;
        loadingIntervalRef.current = setInterval(() => {
            stage++;
            if (stage < LOADING_STAGES.length) setLoadingStage(stage);
            else clearInterval(loadingIntervalRef.current);
        }, 2500);
    };

    const stopLoadingAnimation = () => {
        clearInterval(loadingIntervalRef.current);
        setLoadingStage(LOADING_STAGES.length - 1);
    };

    const loadExample = useCallback(async () => {
        try {
            const ex = await getExampleStrategy();
            setStrategy(ex);
            toast.success('Example strategy loaded');
        } catch (err) {
            if (err?.response?.status === 401) toast.error('Sign in to load the example strategy');
            else toast.error('Failed to load example');
        }
    }, []);

    const handleRun = useCallback(async () => {
        if (!strategy.universe.length) { toast.error('Add at least one ticker'); return; }
        if (!entryConditions.length || !exitConditions.length) { toast.error('Add at least one entry and exit condition'); return; }
        setLoading(true);
        setResult(null);
        setWalkForward(null);
        setResultTab('results');
        startLoadingAnimation();
        try {
            const res = await runBacktest({ strategy, start: startDate, end: endDate, initial_capital: capital });
            setResult(res);
            toast.success(`Backtest complete: ${res.trades?.length || 0} trades`);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Backtest failed');
        } finally {
            stopLoadingAnimation();
            setLoading(false);
        }
    }, [strategy, startDate, endDate, capital, entryConditions.length, exitConditions.length]);

    const handleWalkForward = useCallback(async () => {
        if (!strategy.universe.length) { toast.error('Add at least one ticker'); return; }

        // Bug fix (c): validate date range vs train+test months
        const start = new Date(startDate);
        const end = new Date(endDate);
        const totalMonthsNeeded = wfTrainMonths + wfTestMonths;
        const rangeMonths = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
        if (rangeMonths < totalMonthsNeeded) {
            toast.error(`Date range (${rangeMonths} months) is shorter than train (${wfTrainMonths}) + test (${wfTestMonths}) = ${totalMonthsNeeded} months required`);
            return;
        }

        setLoading(true);
        setResult(null);
        setWalkForward(null);
        setResultTab('walk-forward');
        startLoadingAnimation();
        try {
            const res = await runWalkForward({
                strategy, start: startDate, end: endDate, initial_capital: capital,
                train_months: wfTrainMonths, test_months: wfTestMonths,
            });
            setWalkForward(res);
            toast.success(`Walk-forward complete: ${res.windows?.length || 0} windows`);
        } catch (err) {
            const detail = err.response?.data?.detail;
            toast.error(typeof detail === 'string' ? detail : 'Walk-forward analysis failed. Check your parameters and try again.');
        } finally {
            stopLoadingAnimation();
            setLoading(false);
        }
    }, [strategy, startDate, endDate, capital, wfTrainMonths, wfTestMonths]);

    // Bug fix (a) & (b): applyJson preserves dates and doesn't double-multiply stop/take values
    const applyJson = useCallback(() => {
        try {
            const parsed = JSON.parse(jsonText);
            // Extract dates from JSON if present, otherwise keep current
            const newStart = parsed.start || parsed.startDate;
            const newEnd = parsed.end || parsed.endDate;
            if (newStart) setStartDate(newStart);
            if (newEnd) setEndDate(newEnd);
            // Remove date fields from the strategy object
            const { start, end, startDate: sd, endDate: ed, ...strategyOnly } = parsed;
            setStrategy(strategyOnly);
            setShowJson(false);
            toast.success('Strategy loaded from JSON');
        } catch {
            toast.error('Invalid JSON — check the syntax');
        }
    }, [jsonText]);

    const applyTemplate = useCallback((strat) => {
        setStrategy(strat);
        toast.success(`Loaded: ${strat.name || 'Template'}`);
    }, []);

    const toggleJson = useCallback(() => {
        if (!showJson) setJsonText(JSON.stringify(strategy, null, 2));
        setShowJson(!showJson);
    }, [showJson, strategy]);

    const handleShareUrl = useCallback(() => {
        const encoded = encodeStrategyUrl(strategy, startDate, endDate);
        if (encoded) {
            const url = `${window.location.origin}${window.location.pathname}?strategy=${encoded}`;
            navigator.clipboard.writeText(url);
            toast.success('Shareable URL copied to clipboard');
        }
    }, [strategy, startDate, endDate]);

    const metrics = walkForward ? walkForward.aggregate_oos?.metrics : result?.metrics;
    const equityCurve = walkForward ? walkForward.aggregate_oos?.equity_curve : result?.equity_curve;
    const trades = walkForward ? [] : (result?.trades || []);

    return (
        <TooltipProvider delayDuration={200}>
            <div className="min-h-screen bg-background p-4 md:p-6">
                {/* Market Context Ribbon */}
                <MarketContextRibbon />

                {/* Page Header */}
                <div className="mb-6 flex items-start justify-between">
                    <div>
                        <h1 className="text-2xl font-bold font-mono tracking-tight text-foreground flex items-center gap-3">
                            <FlaskConical className="w-7 h-7 text-primary" />
                            Backtest Lab
                        </h1>
                        <p className="text-sm text-muted-foreground mt-1 font-mono">
                            Build, backtest, and validate quantitative strategies
                            <span className="text-muted-foreground/50 ml-2 text-xs">⌘+Enter to run</span>
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button size="sm" variant="ghost" onClick={handleShareUrl} className="text-xs font-mono gap-1 h-8">
                                    <Share2 className="w-3.5 h-3.5" />Share
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>Copy shareable URL with current strategy</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button size="sm" variant="ghost" onClick={() => setShowPython(true)} className="text-xs font-mono gap-1 h-8">
                                    <Terminal className="w-3.5 h-3.5" />Python
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>Export strategy as Python backtrader script</TooltipContent>
                        </Tooltip>
                    </div>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
                    {/* ── Left Panel: Strategy Editor ── */}
                    <div className="xl:col-span-2 space-y-5">
                        {/* AI Strategy Builder */}
                        <AiStrategyBuilder onApply={applyTemplate} />

                        {/* Strategy Library */}
                        <StrategyLibrary onApply={applyTemplate} currentStrategy={strategy} />

                        {/* Strategy Form */}
                        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-5">
                            <div className="flex items-center justify-between">
                                <h2 className="text-sm font-mono font-semibold text-foreground uppercase tracking-wider">Strategy</h2>
                                <div className="flex items-center gap-2">
                                    <Button size="sm" variant="ghost" onClick={loadExample} className="text-xs font-mono">Example</Button>
                                    <Button size="sm" variant="ghost" onClick={toggleJson} className="text-xs font-mono gap-1">
                                        <Code className="w-3 h-3" />{showJson ? 'Form' : 'JSON'}
                                    </Button>
                                </div>
                            </div>

                            {showJson ? (
                                <div className="space-y-3">
                                    <div className="text-[10px] font-mono text-muted-foreground mb-1">
                                        Values like stop_loss_pct and take_profit_pct should be decimals (e.g. 0.08 = 8%)
                                    </div>
                                    <textarea value={jsonText} onChange={(e) => setJsonText(e.target.value)} rows={20}
                                        className="w-full px-3 py-2 rounded bg-black/30 border border-white/10 text-xs font-mono text-green-400 focus:outline-none focus:ring-1 focus:ring-primary resize-y"
                                        spellCheck={false} />
                                    <Button size="sm" onClick={applyJson} className="text-xs font-mono">Apply JSON</Button>
                                </div>
                            ) : (
                                <>
                                    <div>
                                        <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Strategy Name</label>
                                        <input value={strategy.name} onChange={(e) => setStrategy({ ...strategy, name: e.target.value })}
                                            placeholder="My Strategy"
                                            className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary" />
                                    </div>
                                    <TickerInput tickers={strategy.universe} onChange={(u) => setStrategy({ ...strategy, universe: u })} />
                                    <IndicatorEditor indicators={strategy.indicators} onChange={(ind) => setStrategy({ ...strategy, indicators: ind })} />
                                    <ConditionEditor label="Entry Conditions" conditions={entryConditions} combinator={entryCombinator}
                                        onChange={(entry) => setStrategy({ ...strategy, entry })} isExit={false} />
                                    <ConditionEditor label="Exit Conditions" conditions={exitConditions} combinator={exitCombinator}
                                        onChange={(exit) => setStrategy({ ...strategy, exit })} isExit={true} />

                                    <div className="grid grid-cols-2 gap-3">
                                        <div>
                                            <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Position Sizing</label>
                                            <select value={strategy.position_sizing.type}
                                                onChange={(e) => setStrategy({ ...strategy, position_sizing: { ...strategy.position_sizing, type: e.target.value } })}
                                                className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground">
                                                {SIZING_TYPES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                                            </select>
                                        </div>
                                        {strategy.position_sizing.type === 'fixed_pct' && (
                                            <div>
                                                <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">% per Position</label>
                                                <input type="number" step="0.01" value={(strategy.position_sizing.pct || 0.1) * 100}
                                                    onChange={(e) => setStrategy({ ...strategy, position_sizing: { ...strategy.position_sizing, pct: Number(e.target.value) / 100 } })}
                                                    className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground" />
                                            </div>
                                        )}
                                    </div>

                                    <div className="grid grid-cols-3 gap-3">
                                        <div>
                                            <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Max Positions</label>
                                            <input type="number" value={strategy.max_positions}
                                                onChange={(e) => setStrategy({ ...strategy, max_positions: Number(e.target.value) || 5 })}
                                                className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground" />
                                        </div>
                                        <div>
                                            <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Stop Loss %</label>
                                            <input type="number" step="0.01" value={(strategy.stop_loss_pct || 0) * 100}
                                                onChange={(e) => setStrategy({ ...strategy, stop_loss_pct: Number(e.target.value) / 100 || null })}
                                                className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground" />
                                        </div>
                                        <div>
                                            <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Take Profit %</label>
                                            <input type="number" step="0.01" value={(strategy.take_profit_pct || 0) * 100}
                                                onChange={(e) => setStrategy({ ...strategy, take_profit_pct: Number(e.target.value) / 100 || null })}
                                                className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground" />
                                        </div>
                                    </div>
                                </>
                            )}
                        </div>

                        {/* Run Controls */}
                        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-4">
                            <div className="grid grid-cols-3 gap-3">
                                <div>
                                    <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Start Date</label>
                                    <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                                        className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground" />
                                </div>
                                <div>
                                    <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">End Date</label>
                                    <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                                        className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground" />
                                </div>
                                <div>
                                    <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Capital ($)</label>
                                    <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value) || 100000)}
                                        className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground" />
                                </div>
                            </div>

                            <div className="flex flex-col sm:flex-row gap-3">
                                <Button onClick={handleRun} disabled={loading}
                                    className="flex-1 bg-primary text-primary-foreground hover:bg-primary/90 font-mono text-sm gap-2">
                                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                                    Run Backtest
                                </Button>
                                <Button onClick={handleWalkForward} disabled={loading} variant="outline" className="flex-1 font-mono text-sm gap-2">
                                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Layers className="w-4 h-4" />}
                                    Walk-Forward
                                </Button>
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">WF Train (months)</label>
                                    <input type="number" value={wfTrainMonths} onChange={(e) => setWfTrainMonths(Number(e.target.value) || 36)}
                                        className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground" />
                                </div>
                                <div>
                                    <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">WF Test (months)</label>
                                    <input type="number" value={wfTestMonths} onChange={(e) => setWfTestMonths(Number(e.target.value) || 12)}
                                        className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground" />
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* ── Right Panel: Results ── */}
                    <div className="xl:col-span-3">
                        {/* Empty state */}
                        {!result && !walkForward && !loading && (
                            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-12 text-center">
                                <FlaskConical className="w-16 h-16 text-primary mx-auto mb-4 opacity-50" />
                                <h3 className="text-lg font-semibold text-foreground mb-2 font-mono">No Results Yet</h3>
                                <p className="text-sm text-muted-foreground max-w-md mx-auto font-mono">
                                    Configure your strategy on the left, then click "Run Backtest" or use ⌘+Enter
                                </p>
                                <Button variant="outline" onClick={loadExample} className="mt-6 font-mono text-sm">
                                    Load Example Strategy
                                </Button>
                            </div>
                        )}

                        {/* Loading state */}
                        {loading && <LoadingOverlay stage={loadingStage} />}

                        {/* Results with tabs */}
                        {!loading && (result || walkForward) && (
                            <Tabs value={resultTab} onValueChange={setResultTab}>
                                <TabsList className="bg-white/5 mb-5">
                                    <TabsTrigger value="results" className="text-xs font-mono gap-1.5">
                                        <BarChart3 className="w-3 h-3" />Results
                                    </TabsTrigger>
                                    <TabsTrigger value="risk" className="text-xs font-mono gap-1.5">
                                        <Shield className="w-3 h-3" />Risk Analytics
                                    </TabsTrigger>
                                    <TabsTrigger value="walk-forward" className="text-xs font-mono gap-1.5">
                                        <Layers className="w-3 h-3" />Walk-Forward
                                    </TabsTrigger>
                                    <TabsTrigger value="monte-carlo" className="text-xs font-mono gap-1.5">
                                        <Activity className="w-3 h-3" />Monte Carlo
                                    </TabsTrigger>
                                </TabsList>

                                {/* Results Tab */}
                                <TabsContent value="results">
                                    <div className="space-y-6">
                                        {/* AI Narrative */}
                                        {metrics && result && (
                                            <AiNarrativeCard strategy={strategy} metrics={metrics} trades={trades} />
                                        )}

                                        {/* Metrics Grid */}
                                        {metrics && <MetricsGrid metrics={metrics} trades={trades} />}

                                        {/* Equity Curve */}
                                        {equityCurve?.length > 0 && (
                                            <EquityCurveChart
                                                equityCurve={equityCurve}
                                                startDate={startDate}
                                                endDate={endDate}
                                                capital={capital}
                                            />
                                        )}

                                        {/* Monthly Heatmap */}
                                        {result?.monthly_returns && <MonthlyHeatmap monthlyReturns={result.monthly_returns} />}

                                        {/* Trade Log */}
                                        <TradeLog trades={trades} />
                                    </div>
                                </TabsContent>

                                {/* Risk Analytics Tab */}
                                <TabsContent value="risk">
                                    <RiskAnalyticsPanel metrics={metrics} trades={trades} />
                                </TabsContent>

                                {/* Walk-Forward Tab */}
                                <TabsContent value="walk-forward">
                                    <WalkForwardPanel walkForward={walkForward} />
                                </TabsContent>

                                {/* Monte Carlo Tab */}
                                <TabsContent value="monte-carlo">
                                    <MonteCarloPanel trades={trades} capital={capital} />
                                </TabsContent>
                            </Tabs>
                        )}
                    </div>
                </div>

                {/* Python Code Modal */}
                <PythonCodeModal
                    open={showPython}
                    onClose={() => setShowPython(false)}
                    strategy={strategy}
                    startDate={startDate}
                    endDate={endDate}
                    capital={capital}
                />
            </div>
        </TooltipProvider>
    );
}
