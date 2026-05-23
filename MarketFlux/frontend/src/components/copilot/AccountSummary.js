import { useEffect, useState, useCallback } from 'react';
import { Wallet, TrendingUp, TrendingDown, RefreshCw, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import alpacaApi from '@/lib/alpacaApi';
import api from '@/lib/api';

function fmt(v) {
    if (v == null || !Number.isFinite(Number(v))) return '—';
    return Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

function pct(v) {
    if (v == null || !Number.isFinite(Number(v))) return '—';
    return `${(Number(v) * 100).toFixed(2)}%`;
}

export default function AccountSummary({ refreshSignal = 0, source = 'alpaca' }) {
    const [account, setAccount] = useState(null);
    const [positions, setPositions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            // The copilot source uses no-auth read endpoints on the shared paper
            // account, so the panel works even when the user isn't logged in.
            const [acct, pos] = source === 'copilot'
                ? await Promise.all([
                    api.get('/copilot/account').then((r) => r.data),
                    api.get('/copilot/positions').then((r) => r.data),
                ])
                : await Promise.all([alpacaApi.getAccount(), alpacaApi.getPositions()]);
            setAccount(acct?.item || acct);
            const posList = pos?.items || pos;
            setPositions(Array.isArray(posList) ? posList : []);
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || 'Failed to load account');
        } finally {
            setLoading(false);
        }
    }, [source]);

    useEffect(() => {
        refresh();
        const interval = setInterval(refresh, 30000);
        return () => clearInterval(interval);
    }, [refresh]);

    // Force an immediate refresh when a trade executes (signal bumped by parent).
    useEffect(() => {
        if (refreshSignal > 0) {
            const t = setTimeout(refresh, 800);
            return () => clearTimeout(t);
        }
    }, [refreshSignal, refresh]);

    if (loading && !account) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-6 text-center">
                <Wallet className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-50" />
                <p className="text-sm text-muted-foreground font-mono mb-3">{error}</p>
                <Button size="sm" variant="outline" onClick={refresh} className="text-xs font-mono gap-1">
                    <RefreshCw className="w-3 h-3" /> Retry
                </Button>
            </div>
        );
    }

    const equity = Number(account?.equity || 0);
    const cash = Number(account?.cash || 0);
    // The account payload often omits aggregate P&L — derive it from positions.
    const posPl = positions.reduce((s, p) => s + Number(p.unrealized_pl || 0), 0);
    const posCost = positions.reduce((s, p) => s + Number(p.cost_basis || 0), 0);
    const pl = Number(account?.unrealized_pl || account?.profit_loss) || posPl;
    const plPct = Number(account?.unrealized_plpc || account?.profit_loss_pct) || (posCost ? posPl / posCost : 0);
    const dayPl = Number(account?.equity) - Number(account?.last_equity || account?.equity);

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-mono font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
                    <Wallet className="w-4 h-4 text-primary" />
                    Paper Account
                </h3>
                <Button size="sm" variant="ghost" onClick={refresh} disabled={loading} className="text-xs font-mono h-7">
                    <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                </Button>
            </div>

            <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">Equity</span>
                    <p className="text-lg font-bold font-mono text-foreground">{fmt(equity)}</p>
                </div>
                <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">Cash</span>
                    <p className="text-lg font-bold font-mono text-foreground">{fmt(cash)}</p>
                </div>
                <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">Unrealized P&L</span>
                    <p className={`text-sm font-bold font-mono ${pl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {fmt(pl)} ({pct(plPct)})
                    </p>
                </div>
                <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">Day P&L</span>
                    <p className={`text-sm font-bold font-mono ${dayPl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {fmt(dayPl)}
                    </p>
                </div>
            </div>

            {positions.length > 0 && (
                <div>
                    <h4 className="text-xs font-mono text-muted-foreground uppercase tracking-wider mb-2">
                        Positions ({positions.length})
                    </h4>
                    <div className="space-y-1.5">
                        {positions.map((p) => {
                            const positionPl = Number(p.unrealized_pl || 0);
                            return (
                                <div key={p.symbol} className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
                                    <div>
                                        <span className="text-sm font-mono font-semibold text-primary">{p.symbol}</span>
                                        <span className="text-xs font-mono text-muted-foreground ml-2">
                                            {p.qty} @ {fmt(p.avg_entry_price)}
                                        </span>
                                    </div>
                                    <div className="text-right">
                                        <span className={`text-xs font-mono font-semibold ${positionPl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {positionPl >= 0 ? <TrendingUp className="w-3 h-3 inline mr-1" /> : <TrendingDown className="w-3 h-3 inline mr-1" />}
                                            {fmt(positionPl)}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {positions.length === 0 && (
                <p className="text-xs font-mono text-muted-foreground text-center py-4">No open positions</p>
            )}
        </div>
    );
}
