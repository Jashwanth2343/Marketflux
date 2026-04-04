import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Activity, ArrowRight, Clock3, SearchCheck,
  ShieldCheck, TerminalSquare, AlertTriangle, RefreshCw, FileText
} from 'lucide-react';

import SearchBar from '@/components/SearchBar';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import api from '@/lib/api';

const POLL_INTERVAL_MS = 25000;

function formatTimestamp(value) {
  if (!value) return '--';
  try {
    return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return value;
  }
}

function StatusBadge({ status }) {
  const s = status || '';
  const isPending = s === 'pending_approval' || s === 'generated';
  const isApproved = s === 'approved' || s === 'paper_open';
  const isRejected = s === 'rejected' || s === 'blocked';
  
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-mono uppercase tracking-[0.14em] ${
      isApproved ? 'bg-[#00ff88]/10 text-[#00ff88]' :
      isRejected ? 'bg-destructive/10 text-destructive' :
      'bg-primary/10 text-primary'
    }`}>
      {s.replace(/_/g, ' ')}
    </span>
  );
}

export default function FundOS() {
  const navigate = useNavigate();
  const [overview, setOverview] = useState(null);
  const [queue, setQueue] = useState({ items: [], total: 0 });
  const [portfolio, setPortfolio] = useState({ configured: false, positions: [], message: '' });
  const [auditLog, setAuditLog] = useState({ items: [] });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const fetchAll = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);

    try {
      const [ovRes, qRes, pRes, aRes] = await Promise.all([
        api.get('/fundos/overview'),
        api.get('/fundos/strategies/queue'),
        api.get('/fundos/portfolio/paper'),
        api.get('/fundos/audit-feed')
      ]);
      setOverview(ovRes.data);
      setQueue(qRes.data);
      setPortfolio(pRes.data);
      setAuditLog(aRes.data);
      setError(null);
    } catch (err) {
      console.error(err);
      setError('Fund OS services are temporarily unavailable. Please configure NEMOCLAW_OPENCLAW_URL if terminal is failing.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const timer = setInterval(() => fetchAll(true), POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [fetchAll]);

  const handleActionClick = async (strategyId, action) => {
    try {
      await api.post(`/fundos/strategies/${strategyId}/${action}`);
      fetchAll(true);
    } catch (err) {
      alert(err.response?.data?.detail || `Failed to process ${action}`);
    }
  };

  return (
    <div className="fundos-shell p-4 md:p-6 lg:p-8" data-testid="fund-os-page">
      <div className="mx-auto max-w-7xl space-y-6">
        
        {/* Header Section */}
        <Card className="fundos-card rounded-[32px]">
          <CardContent className="p-6 md:p-8 lg:p-10">
            <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr] lg:items-end">
              <div className="space-y-6">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="fundos-badge">
                    <Activity className="w-3.5 h-3.5" />
                    Fund OS Platform
                  </div>
                  {overview && (
                    <div className="rounded-full border border-white/10 bg-white/4 px-3 py-1 text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
                      Updated {formatTimestamp(overview.as_of)}
                    </div>
                  )}
                </div>

                <div>
                  <h1 className="fundos-display max-w-4xl text-4xl font-semibold leading-[1.05] text-foreground md:text-5xl">
                    Isolated Strategy Execution Layer
                  </h1>
                  <p className="mt-4 max-w-2xl text-base leading-8 text-muted-foreground md:text-lg">
                    Manage and approve terminal-generated strategies. Fund OS operates strictly on isolated infrastructure to ensure retail MarketFlux endpoints remain secure and separate.
                  </p>
                </div>

                <div className="max-w-3xl">
                  <SearchBar variant="hero" />
                </div>

                <div className="flex flex-wrap gap-3">
                  <Button
                    onClick={() => navigate('/fund-os/terminal')}
                    className="h-12 rounded-full px-6 text-sm font-semibold"
                  >
                    <TerminalSquare className="w-4 h-4 mr-2" />
                    Open Terminal
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => fetchAll(true)}
                    className="h-12 rounded-full border-white/10 bg-white/4 px-6 text-sm font-semibold text-foreground hover:bg-white/8"
                  >
                    <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
                    Refresh Data
                  </Button>
                </div>
              </div>

               {/* Quick Metrics */}
               <div className="grid gap-4 md:grid-cols-2">
                <div className="fundos-metric p-4">
                  <div className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">Queued Strategies</div>
                  <div className="mt-2 fundos-display text-3xl font-semibold text-foreground">{queue.total}</div>
                  <div className="mt-1 text-sm text-muted-foreground">Pending human review</div>
                </div>
                <div className="fundos-metric p-4">
                  <div className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">Terminal</div>
                  <div className="mt-2 fundos-display text-3xl font-semibold text-foreground">
                     {overview?.terminal_status === 'pending_openclaw' ? 'Standby' : 'Active'}
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">Awaiting cloud deployment</div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {error && (
          <Card className="rounded-[24px] border border-destructive/30 bg-destructive/10">
            <CardContent className="flex items-center gap-3 p-4 text-sm text-destructive">
              <AlertTriangle className="w-4 h-4" />
              {error}
            </CardContent>
          </Card>
        )}

        <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          
          <div className="space-y-6">
            {/* Strategy Queue */}
            <Card className="fundos-card rounded-[28px]">
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="fundos-kicker">Execution pipeline</div>
                    <CardTitle className="fundos-display mt-3 text-3xl font-semibold text-foreground">Strategy Queue</CardTitle>
                  </div>
                  <FileText className="w-6 h-6 text-primary" />
                </div>
              </CardHeader>
              <CardContent>
                {queue.items.length === 0 && !loading ? (
                  <div className="rounded-[18px] border border-dashed border-white/10 bg-white/4 px-4 py-8 text-center text-sm leading-7 text-muted-foreground">
                    <p>No active strategies found in the queue.</p>
                    <Button variant="link" onClick={() => navigate('/fund-os/terminal')} className="mt-2 text-primary font-semibold">
                      Run your first strategy via Terminal →
                    </Button>
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-[18px] border border-white/8 bg-white/4">
                    <Table>
                      <TableHeader className="bg-white/5">
                        <TableRow className="border-white/10">
                          <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Focus</TableHead>
                          <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Strategy</TableHead>
                          <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Status</TableHead>
                          <TableHead className="text-right text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Execution</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {queue.items.map((item) => (
                          <TableRow key={item.strategy_id} className="border-white/10">
                            <TableCell className="font-mono text-sm text-foreground/90">{item.focus || item.ticker || '---'}</TableCell>
                            <TableCell className="font-medium max-w-[200px] truncate text-foreground">
                              <Link to={`/fund-os/terminal/${item.strategy_id}`} className="hover:underline text-primary transition-colors">
                                {item.title}
                              </Link>
                            </TableCell>
                            <TableCell>
                              <StatusBadge status={item.status} />
                            </TableCell>
                            <TableCell className="text-right py-3">
                              {item.status === 'pending_approval' || item.status === 'generated' ? (
                                <div className="flex items-center justify-end gap-2">
                                  <Button size="sm" variant="outline" className="h-8 rounded-full border-primary/20 bg-primary/10 text-primary hover:bg-primary/20 text-xs font-semibold px-4" onClick={() => handleActionClick(item.strategy_id, 'approve')}>
                                    Approve
                                  </Button>
                                  <Button size="sm" variant="destructive" className="h-8 rounded-full bg-destructive/20 text-destructive hover:bg-destructive/40 text-xs font-semibold px-4" onClick={() => handleActionClick(item.strategy_id, 'reject')}>
                                    Reject
                                  </Button>
                                </div>
                              ) : (
                                <span className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Finalized</span>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Paper Portfolio */}
            <Card className="fundos-card rounded-[28px]">
               <CardHeader className="pb-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="fundos-kicker">Live tracking</div>
                    <CardTitle className="fundos-display mt-3 text-3xl font-semibold text-foreground">Paper Portfolio</CardTitle>
                  </div>
                  <ShieldCheck className="w-6 h-6 text-primary" />
                </div>
              </CardHeader>
              <CardContent>
                {!portfolio.configured ? (
                  <div className="rounded-[18px] border border-dashed border-destructive/20 bg-destructive/5 p-6 text-sm text-destructive">
                    {portfolio.message || "Fund OS storage is not wired. Add FUNDOS_DATABASE_URL to enable paper trading executions."}
                  </div>
                ) : (
                  portfolio.positions.length > 0 ? (
                    <div className="overflow-x-auto rounded-[18px] border border-white/8 bg-white/4">
                      <Table>
                        <TableHeader className="bg-white/5">
                          <TableRow className="border-white/10">
                            <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Symbol</TableHead>
                            <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Qty</TableHead>
                            <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Avg Price</TableHead>
                            <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Mark</TableHead>
                            <TableHead className="text-right text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Unrealized</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {portfolio.positions.map((pos) => (
                            <TableRow key={pos.symbol} className="border-white/10">
                              <TableCell className="font-bold text-foreground">{pos.symbol}</TableCell>
                              <TableCell className="text-foreground/90">{pos.quantity}</TableCell>
                              <TableCell className="text-foreground/90">${pos.avg_price}</TableCell>
                              <TableCell className="text-foreground/90">${pos.mark_price}</TableCell>
                              <TableCell className={`text-right font-mono text-sm ${pos.unrealized_pnl >= 0 ? 'text-[#00ff88]' : 'text-destructive'}`}>
                                ${pos.unrealized_pnl}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <div className="rounded-[18px] border border-white/8 bg-white/4 p-6 text-sm text-muted-foreground">
                      Portfolio configured successfully, but no open positions yet.
                    </div>
                  )
                )}
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            {/* Audit Log */}
            <Card className="fundos-card rounded-[28px]">
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="fundos-kicker">Traceability</div>
                    <CardTitle className="fundos-display mt-3 text-3xl font-semibold text-foreground">Audit Feed</CardTitle>
                  </div>
                  <Clock3 className="w-6 h-6 text-primary" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {!auditLog.items.length ? (
                    <div className="rounded-[18px] border border-white/8 bg-white/4 p-4 text-sm text-muted-foreground">
                      No recent actions logged.
                    </div>
                  ) : (
                    auditLog.items.map((log, idx) => (
                      <div key={idx} className="rounded-[20px] border border-white/8 bg-white/4 p-4">
                        <div className="flex items-center justify-between gap-4 text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
                          <span className="text-primary">{log.event_type.replace(/_/g, ' ')}</span>
                          <span>{formatTimestamp(log.timestamp)}</span>
                        </div>
                        <div className="mt-2 text-sm leading-6 text-foreground/90">{log.summary}</div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
          
        </div>
      </div>
    </div>
  );
}
