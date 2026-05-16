import { useState, useCallback } from 'react';
import { FlaskConical, Play, BarChart3, TrendingUp, TrendingDown, AlertTriangle, Loader2, Code, Layers, X, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { getExampleStrategy, runBacktest, runWalkForward } from '@/lib/backtestApi';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

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

function TickerInput({ tickers, onChange }) {
    const [input, setInput] = useState('');

    const addTicker = () => {
        const t = input.trim().toUpperCase();
        if (t && !tickers.includes(t)) {
            onChange([...tickers, t]);
        }
        setInput('');
    };

    return (
        <div>
            <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Universe</label>
            <div className="flex flex-wrap gap-1.5 mt-1 mb-2">
                {tickers.map((t) => (
                    <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-primary/15 text-primary text-xs font-mono">
                        {t}
                        <button onClick={() => onChange(tickers.filter((x) => x !== t))} className="hover:text-red-400">
                            <X className="w-3 h-3" />
                        </button>
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
                            <input
                                value={name}
                                onChange={(e) => renameIndicator(name, e.target.value)}
                                className="w-24 px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                            />
                            <select
                                value={spec.type}
                                onChange={(e) => updateIndicator(name, 'type', e.target.value)}
                                className="px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground focus:outline-none"
                            >
                                {INDICATOR_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                            </select>
                            {typeDef?.params.filter((p) => p !== 'source').map((p) => (
                                <input
                                    key={p}
                                    type="number"
                                    placeholder={p}
                                    value={spec[p] ?? ''}
                                    onChange={(e) => updateIndicator(name, p, e.target.value ? Number(e.target.value) : undefined)}
                                    className="w-16 px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground placeholder:text-muted-foreground focus:outline-none"
                                />
                            ))}
                            <button onClick={() => removeIndicator(name)} className="text-muted-foreground hover:text-red-400 ml-auto"><X className="w-3.5 h-3.5" /></button>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function ConditionEditor({ label, conditions, combinator, onChange, isExit }) {
    const addCondition = () => {
        onChange({ [combinator]: [...conditions, { gt: ['close', 0] }] });
    };

    const removeCondition = (idx) => {
        const next = conditions.filter((_, i) => i !== idx);
        onChange({ [combinator]: next });
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
                    <select
                        value={combinator}
                        onChange={(e) => onChange({ [e.target.value]: conditions })}
                        className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground"
                    >
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
                                <select
                                    value={op}
                                    onChange={(e) => {
                                        const newOp = e.target.value;
                                        if (['hold_days_gte', 'profit_pct_gte', 'loss_pct_gte'].includes(newOp)) {
                                            updateCondition(idx, { [newOp]: val });
                                        } else {
                                            updateCondition(idx, { [newOp]: ['close', 0] });
                                        }
                                    }}
                                    className="px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground"
                                >
                                    {COMPARATORS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                                    {isExit && <>
                                        <option value="hold_days_gte">Hold Days >=</option>
                                        <option value="profit_pct_gte">Profit % >=</option>
                                        <option value="loss_pct_gte">Loss % >=</option>
                                    </>}
                                </select>
                                <input
                                    type="number"
                                    value={val}
                                    onChange={(e) => updateCondition(idx, { [op]: Number(e.target.value) || 0 })}
                                    className="w-20 px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground"
                                />
                                <button onClick={() => removeCondition(idx)} className="text-muted-foreground hover:text-red-400 ml-auto"><X className="w-3.5 h-3.5" /></button>
                            </div>
                        );
                    }

                    return (
                        <div key={idx} className="flex items-center gap-2 p-2 rounded bg-white/[0.03] border border-white/5">
                            <input
                                value={Array.isArray(val) ? val[0] : ''}
                                onChange={(e) => updateCondition(idx, { [op]: [e.target.value, Array.isArray(val) ? val[1] : 0] })}
                                placeholder="lhs"
                                className="w-24 px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground placeholder:text-muted-foreground"
                            />
                            <select
                                value={op}
                                onChange={(e) => {
                                    const newOp = e.target.value;
                                    if (['hold_days_gte', 'profit_pct_gte', 'loss_pct_gte'].includes(newOp)) {
                                        updateCondition(idx, { [newOp]: 20 });
                                    } else {
                                        updateCondition(idx, { [newOp]: val });
                                    }
                                }}
                                className="px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground"
                            >
                                {COMPARATORS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                                {isExit && <>
                                    <option value="hold_days_gte">Hold Days >=</option>
                                    <option value="profit_pct_gte">Profit % >=</option>
                                    <option value="loss_pct_gte">Loss % >=</option>
                                </>}
                            </select>
                            <input
                                value={Array.isArray(val) ? val[1] : ''}
                                onChange={(e) => {
                                    const v = e.target.value;
                                    const parsed = isNaN(Number(v)) ? v : Number(v);
                                    updateCondition(idx, { [op]: [Array.isArray(val) ? val[0] : '', parsed] });
                                }}
                                placeholder="rhs"
                                className="w-24 px-2 py-1 rounded bg-white/5 border border-white/10 text-xs font-mono text-foreground placeholder:text-muted-foreground"
                            />
                            <button onClick={() => removeCondition(idx)} className="text-muted-foreground hover:text-red-400 ml-auto"><X className="w-3.5 h-3.5" /></button>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function MetricCard({ label, value, icon: Icon, color = 'text-primary' }) {
    return (
        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
            <div className="flex items-center gap-2 mb-1">
                {Icon && <Icon className={`w-3.5 h-3.5 ${color}`} />}
                <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">{label}</span>
            </div>
            <p className={`text-lg font-bold font-mono ${color}`}>{value}</p>
        </div>
    );
}

function fmt(v, type = 'pct') {
    if (v == null || isNaN(v)) return '—';
    if (type === 'pct') return `${(v * 100).toFixed(2)}%`;
    if (type === 'ratio') return v.toFixed(2);
    if (type === 'money') return `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (type === 'int') return Math.round(v).toLocaleString();
    return String(v);
}

function ResultsPanel({ result, walkForward }) {
    if (!result && !walkForward) return null;

    const metrics = walkForward ? walkForward.aggregate_oos?.metrics : result?.metrics;
    const equityCurve = walkForward ? walkForward.aggregate_oos?.equity_curve : result?.equity_curve;
    const trades = walkForward ? [] : (result?.trades || []);

    return (
        <div className="space-y-6">
            {metrics && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <MetricCard label="Total Return" value={fmt(metrics.total_return)} icon={TrendingUp} color={metrics.total_return >= 0 ? 'text-green-400' : 'text-red-400'} />
                    <MetricCard label="CAGR" value={fmt(metrics.cagr)} icon={TrendingUp} color={metrics.cagr >= 0 ? 'text-green-400' : 'text-red-400'} />
                    <MetricCard label="Sharpe" value={fmt(metrics.sharpe, 'ratio')} icon={BarChart3} />
                    <MetricCard label="Sortino" value={fmt(metrics.sortino, 'ratio')} icon={BarChart3} />
                    <MetricCard label="Max Drawdown" value={fmt(metrics.max_drawdown)} icon={TrendingDown} color="text-red-400" />
                    <MetricCard label="Volatility" value={fmt(metrics.volatility)} icon={AlertTriangle} />
                    <MetricCard label="Win Rate" value={fmt(metrics.win_rate)} icon={TrendingUp} />
                    <MetricCard label="Trades" value={fmt(metrics.num_trades, 'int')} icon={Layers} />
                    <MetricCard label="Profit Factor" value={fmt(metrics.profit_factor, 'ratio')} icon={BarChart3} />
                    <MetricCard label="Expectancy" value={fmt(metrics.expectancy, 'money')} icon={TrendingUp} color={metrics.expectancy >= 0 ? 'text-green-400' : 'text-red-400'} />
                    <MetricCard label="Avg Trade P&L" value={fmt(metrics.avg_trade_pnl, 'money')} icon={BarChart3} />
                    {result && <MetricCard label="Final Equity" value={fmt(result.final_equity, 'money')} icon={TrendingUp} color="text-primary" />}
                </div>
            )}

            {equityCurve?.length > 0 && (
                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
                    <h3 className="text-sm font-mono font-semibold text-foreground mb-4">
                        {walkForward ? 'Out-of-Sample Equity Curve' : 'Equity Curve'}
                    </h3>
                    <ResponsiveContainer width="100%" height={300}>
                        <AreaChart data={equityCurve}>
                            <defs>
                                <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                            <XAxis
                                dataKey="date"
                                tick={{ fontSize: 10, fontFamily: 'monospace', fill: 'hsl(var(--muted-foreground))' }}
                                tickFormatter={(d) => d?.slice(0, 10)}
                                interval="preserveStartEnd"
                                minTickGap={80}
                            />
                            <YAxis
                                tick={{ fontSize: 10, fontFamily: 'monospace', fill: 'hsl(var(--muted-foreground))' }}
                                tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                                width={60}
                            />
                            <Tooltip
                                contentStyle={{ background: 'hsl(var(--card))', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontFamily: 'monospace', fontSize: '12px' }}
                                formatter={(v) => [`$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`, 'Equity']}
                                labelFormatter={(d) => d?.slice(0, 10)}
                            />
                            <Area type="monotone" dataKey="equity" stroke="hsl(var(--primary))" fill="url(#eqGrad)" strokeWidth={2} dot={false} />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            )}

            {walkForward?.windows?.length > 0 && (
                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
                    <h3 className="text-sm font-mono font-semibold text-foreground mb-3">Walk-Forward Windows</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-xs font-mono">
                            <thead>
                                <tr className="text-muted-foreground border-b border-white/10">
                                    <th className="text-left py-2 px-2">#</th>
                                    <th className="text-left py-2 px-2">Train</th>
                                    <th className="text-left py-2 px-2">Test</th>
                                    <th className="text-right py-2 px-2">IS Return</th>
                                    <th className="text-right py-2 px-2">OOS Return</th>
                                    <th className="text-right py-2 px-2">OOS Sharpe</th>
                                </tr>
                            </thead>
                            <tbody>
                                {walkForward.windows.map((w, i) => (
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

            {trades.length > 0 && (
                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
                    <h3 className="text-sm font-mono font-semibold text-foreground mb-3">Trade Log ({trades.length})</h3>
                    <div className="overflow-x-auto max-h-80 overflow-y-auto">
                        <table className="w-full text-xs font-mono">
                            <thead className="sticky top-0 bg-card">
                                <tr className="text-muted-foreground border-b border-white/10">
                                    <th className="text-left py-2 px-2">Symbol</th>
                                    <th className="text-left py-2 px-2">Entry</th>
                                    <th className="text-left py-2 px-2">Exit</th>
                                    <th className="text-right py-2 px-2">Entry $</th>
                                    <th className="text-right py-2 px-2">Exit $</th>
                                    <th className="text-right py-2 px-2">Shares</th>
                                    <th className="text-right py-2 px-2">P&L</th>
                                    <th className="text-right py-2 px-2">Return</th>
                                    <th className="text-right py-2 px-2">Bars</th>
                                    <th className="text-left py-2 px-2">Reason</th>
                                </tr>
                            </thead>
                            <tbody>
                                {trades.map((t, i) => (
                                    <tr key={i} className="border-b border-white/5 hover:bg-white/[0.02]">
                                        <td className="py-1.5 px-2 text-primary">{t.symbol}</td>
                                        <td className="py-1.5 px-2">{t.entry_date?.slice(0, 10)}</td>
                                        <td className="py-1.5 px-2">{t.exit_date?.slice(0, 10)}</td>
                                        <td className="py-1.5 px-2 text-right">{fmt(t.entry_price, 'money')}</td>
                                        <td className="py-1.5 px-2 text-right">{fmt(t.exit_price, 'money')}</td>
                                        <td className="py-1.5 px-2 text-right">{Math.round(t.shares)}</td>
                                        <td className={`py-1.5 px-2 text-right ${t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {fmt(t.pnl, 'money')}
                                        </td>
                                        <td className={`py-1.5 px-2 text-right ${t.return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {fmt(t.return_pct)}
                                        </td>
                                        <td className="py-1.5 px-2 text-right">{t.bars_held}</td>
                                        <td className="py-1.5 px-2 text-muted-foreground">{t.exit_reason}</td>
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

export default function Backtest() {
    const [strategy, setStrategy] = useState(defaultStrategy);
    const [startDate, setStartDate] = useState('2020-01-01');
    const [endDate, setEndDate] = useState('2024-01-01');
    const [capital, setCapital] = useState(100000);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [walkForward, setWalkForward] = useState(null);
    const [showJson, setShowJson] = useState(false);
    const [jsonText, setJsonText] = useState('');
    const [wfTrainMonths, setWfTrainMonths] = useState(36);
    const [wfTestMonths, setWfTestMonths] = useState(12);

    const entryCombinator = Object.keys(strategy.entry)[0] || 'all';
    const entryConditions = strategy.entry[entryCombinator] || [];
    const exitCombinator = Object.keys(strategy.exit)[0] || 'any';
    const exitConditions = strategy.exit[exitCombinator] || [];

    const loadExample = useCallback(async () => {
        try {
            const ex = await getExampleStrategy();
            setStrategy(ex);
            toast.success('Example strategy loaded');
        } catch {
            toast.error('Failed to load example');
        }
    }, []);

    const handleRun = useCallback(async () => {
        if (!strategy.universe.length) {
            toast.error('Add at least one ticker');
            return;
        }
        if (!entryConditions.length || !exitConditions.length) {
            toast.error('Add at least one entry and exit condition');
            return;
        }
        setLoading(true);
        setResult(null);
        setWalkForward(null);
        try {
            const res = await runBacktest({ strategy, start: startDate, end: endDate, initial_capital: capital });
            setResult(res);
            toast.success(`Backtest complete: ${res.trades?.length || 0} trades`);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Backtest failed');
        } finally {
            setLoading(false);
        }
    }, [strategy, startDate, endDate, capital, entryConditions.length, exitConditions.length]);

    const handleWalkForward = useCallback(async () => {
        if (!strategy.universe.length) {
            toast.error('Add at least one ticker');
            return;
        }
        setLoading(true);
        setResult(null);
        setWalkForward(null);
        try {
            const res = await runWalkForward({
                strategy, start: startDate, end: endDate, initial_capital: capital,
                train_months: wfTrainMonths, test_months: wfTestMonths,
            });
            setWalkForward(res);
            toast.success(`Walk-forward complete: ${res.windows?.length || 0} windows`);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Walk-forward failed');
        } finally {
            setLoading(false);
        }
    }, [strategy, startDate, endDate, capital, wfTrainMonths, wfTestMonths]);

    const applyJson = useCallback(() => {
        try {
            const parsed = JSON.parse(jsonText);
            setStrategy(parsed);
            setShowJson(false);
            toast.success('Strategy loaded from JSON');
        } catch {
            toast.error('Invalid JSON');
        }
    }, [jsonText]);

    const toggleJson = useCallback(() => {
        if (!showJson) setJsonText(JSON.stringify(strategy, null, 2));
        setShowJson(!showJson);
    }, [showJson, strategy]);

    return (
        <div className="min-h-screen bg-background p-4 md:p-6">
            <div className="mb-6">
                <h1 className="text-2xl font-bold font-mono tracking-tight text-foreground flex items-center gap-3">
                    <FlaskConical className="w-7 h-7 text-primary" />
                    Backtest Lab
                </h1>
                <p className="text-sm text-muted-foreground mt-1 font-mono">
                    Build strategies with a visual DSL editor, run backtests and walk-forward analysis
                </p>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
                {/* Left Panel: Strategy Editor */}
                <div className="xl:col-span-2 space-y-5">
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
                                <textarea
                                    value={jsonText}
                                    onChange={(e) => setJsonText(e.target.value)}
                                    rows={20}
                                    className="w-full px-3 py-2 rounded bg-black/30 border border-white/10 text-xs font-mono text-green-400 focus:outline-none focus:ring-1 focus:ring-primary resize-y"
                                    spellCheck={false}
                                />
                                <Button size="sm" onClick={applyJson} className="text-xs font-mono">Apply JSON</Button>
                            </div>
                        ) : (
                            <>
                                <div>
                                    <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Strategy Name</label>
                                    <input
                                        value={strategy.name}
                                        onChange={(e) => setStrategy({ ...strategy, name: e.target.value })}
                                        placeholder="My Strategy"
                                        className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                                    />
                                </div>

                                <TickerInput tickers={strategy.universe} onChange={(u) => setStrategy({ ...strategy, universe: u })} />
                                <IndicatorEditor indicators={strategy.indicators} onChange={(ind) => setStrategy({ ...strategy, indicators: ind })} />

                                <ConditionEditor
                                    label="Entry Conditions"
                                    conditions={entryConditions}
                                    combinator={entryCombinator}
                                    onChange={(entry) => setStrategy({ ...strategy, entry })}
                                    isExit={false}
                                />
                                <ConditionEditor
                                    label="Exit Conditions"
                                    conditions={exitConditions}
                                    combinator={exitCombinator}
                                    onChange={(exit) => setStrategy({ ...strategy, exit })}
                                    isExit={true}
                                />

                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Position Sizing</label>
                                        <select
                                            value={strategy.position_sizing.type}
                                            onChange={(e) => setStrategy({ ...strategy, position_sizing: { ...strategy.position_sizing, type: e.target.value } })}
                                            className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground"
                                        >
                                            {SIZING_TYPES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                                        </select>
                                    </div>
                                    {strategy.position_sizing.type === 'fixed_pct' && (
                                        <div>
                                            <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">% per Position</label>
                                            <input
                                                type="number"
                                                step="0.01"
                                                value={(strategy.position_sizing.pct || 0.1) * 100}
                                                onChange={(e) => setStrategy({ ...strategy, position_sizing: { ...strategy.position_sizing, pct: Number(e.target.value) / 100 } })}
                                                className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground"
                                            />
                                        </div>
                                    )}
                                </div>

                                <div className="grid grid-cols-3 gap-3">
                                    <div>
                                        <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Max Positions</label>
                                        <input
                                            type="number"
                                            value={strategy.max_positions}
                                            onChange={(e) => setStrategy({ ...strategy, max_positions: Number(e.target.value) || 5 })}
                                            className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Stop Loss %</label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            value={(strategy.stop_loss_pct || 0) * 100}
                                            onChange={(e) => setStrategy({ ...strategy, stop_loss_pct: Number(e.target.value) / 100 || null })}
                                            className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground"
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Take Profit %</label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            value={(strategy.take_profit_pct || 0) * 100}
                                            onChange={(e) => setStrategy({ ...strategy, take_profit_pct: Number(e.target.value) / 100 || null })}
                                            className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground"
                                        />
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
                                <input
                                    type="date"
                                    value={startDate}
                                    onChange={(e) => setStartDate(e.target.value)}
                                    className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground"
                                />
                            </div>
                            <div>
                                <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">End Date</label>
                                <input
                                    type="date"
                                    value={endDate}
                                    onChange={(e) => setEndDate(e.target.value)}
                                    className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground"
                                />
                            </div>
                            <div>
                                <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Capital ($)</label>
                                <input
                                    type="number"
                                    value={capital}
                                    onChange={(e) => setCapital(Number(e.target.value) || 100000)}
                                    className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground"
                                />
                            </div>
                        </div>

                        <div className="flex flex-col sm:flex-row gap-3">
                            <Button
                                onClick={handleRun}
                                disabled={loading}
                                className="flex-1 bg-primary text-primary-foreground hover:bg-primary/90 font-mono text-sm gap-2"
                            >
                                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                                Run Backtest
                            </Button>
                            <Button
                                onClick={handleWalkForward}
                                disabled={loading}
                                variant="outline"
                                className="flex-1 font-mono text-sm gap-2"
                            >
                                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Layers className="w-4 h-4" />}
                                Walk-Forward
                            </Button>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">WF Train (months)</label>
                                <input
                                    type="number"
                                    value={wfTrainMonths}
                                    onChange={(e) => setWfTrainMonths(Number(e.target.value) || 36)}
                                    className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground"
                                />
                            </div>
                            <div>
                                <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">WF Test (months)</label>
                                <input
                                    type="number"
                                    value={wfTestMonths}
                                    onChange={(e) => setWfTestMonths(Number(e.target.value) || 12)}
                                    className="w-full mt-1 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-sm font-mono text-foreground"
                                />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Panel: Results */}
                <div className="xl:col-span-3">
                    {!result && !walkForward && !loading && (
                        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-12 text-center">
                            <FlaskConical className="w-16 h-16 text-primary mx-auto mb-4 opacity-50" />
                            <h3 className="text-lg font-semibold text-foreground mb-2 font-mono">No Results Yet</h3>
                            <p className="text-sm text-muted-foreground max-w-md mx-auto font-mono">
                                Configure your strategy on the left, then click "Run Backtest" or "Walk-Forward" to see results.
                            </p>
                            <Button variant="outline" onClick={loadExample} className="mt-6 font-mono text-sm">
                                Load Example Strategy
                            </Button>
                        </div>
                    )}
                    {loading && (
                        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-12 text-center">
                            <Loader2 className="w-12 h-12 text-primary mx-auto mb-4 animate-spin" />
                            <h3 className="text-lg font-semibold text-foreground mb-2 font-mono">Running...</h3>
                            <p className="text-sm text-muted-foreground font-mono">Fetching market data and simulating trades</p>
                        </div>
                    )}
                    {!loading && <ResultsPanel result={result} walkForward={walkForward} />}
                </div>
            </div>
        </div>
    );
}
