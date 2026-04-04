import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  Beaker,
  Loader2,
  Lock,
  ShieldCheck,
  Target,
} from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '@/contexts/AuthContext';
import thesisApi from '@/lib/thesisApi';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const POLICY_DEFS = [
  { rule_type: 'no_live_trading', label: 'No live trading', description: 'Hard-default simulated only mode.', paramKey: 'value', kind: 'boolean' },
  { rule_type: 'max_position_pct', label: 'Max position size %', description: 'Maximum size for a single new paper trade.', paramKey: 'value', kind: 'number' },
  { rule_type: 'max_gross_exposure_pct', label: 'Max gross exposure %', description: 'Caps total simulated exposure across open trades.', paramKey: 'value', kind: 'number' },
  { rule_type: 'max_single_name_concentration', label: 'Max single-name concentration %', description: 'Prevents thesis concentration from becoming too large.', paramKey: 'value', kind: 'number' },
  { rule_type: 'block_during_earnings_window', label: 'Block during earnings window', description: 'Prevents new positions near earnings.', paramKey: 'days_before', kind: 'number_secondary', secondaryKey: 'days_after' },
  { rule_type: 'max_open_trades', label: 'Max open trades', description: 'Upper bound on simultaneous paper positions.', paramKey: 'value', kind: 'number' },
  { rule_type: 'min_confidence_to_trade', label: 'Minimum evidence confidence %', description: 'Requires evidence confidence to clear a threshold.', paramKey: 'value', kind: 'number' },
];

function formatDate(value) {
  if (!value) return '--';
  try {
    return new Date(value).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

function formatMoney(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return '--';
  return `$${num.toFixed(2)}`;
}

function formatPercent(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return '--';
  return `${num.toFixed(0)}%`;
}

function toPolicyArray(effective) {
  return POLICY_DEFS.map((definition) => {
    const current = effective?.[definition.rule_type] || {};
    return {
      rule_type: definition.rule_type,
      enabled: current.enabled ?? (definition.rule_type === 'no_live_trading'),
      params: current.params || {},
    };
  });
}

function averageConfidence(evidenceBlocks) {
  const nums = (evidenceBlocks || [])
    .map((item) => Number(item.confidence))
    .filter((value) => !Number.isNaN(value));
  if (!nums.length) return null;
  return nums.reduce((sum, value) => sum + value, 0) / nums.length;
}

export default function ThesisTradeLab() {
  const { thesisId } = useParams();
  const navigate = useNavigate();
  const { user, loading } = useAuth();
  const [workspace, setWorkspace] = useState(null);
  const [policyItems, setPolicyItems] = useState([]);
  const [fetching, setFetching] = useState(true);
  const [savingPolicies, setSavingPolicies] = useState(false);
  const [submittingTrade, setSubmittingTrade] = useState(false);
  const [blockedResult, setBlockedResult] = useState(null);
  const [tradeForm, setTradeForm] = useState({
    side: 'buy',
    size: '5',
    notes: '',
  });

  const loadData = useCallback(async () => {
    if (!user) return;
    setFetching(true);
    try {
      const [thesisRes, policyRes] = await Promise.all([
        thesisApi.getThesis(thesisId),
        thesisApi.getPolicies(),
      ]);
      setWorkspace(thesisRes.item);
      setPolicyItems(toPolicyArray(policyRes.effective));
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Unable to load trade lab.');
    } finally {
      setFetching(false);
    }
  }, [thesisId, user]);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      setFetching(false);
      return;
    }
    loadData();
  }, [loading, user, loadData]);

  const thesis = workspace?.thesis;
  const avgConfidence = useMemo(
    () => averageConfidence(workspace?.evidence_blocks || []),
    [workspace],
  );

  const updatePolicy = (ruleType, updater) => {
    setPolicyItems((current) =>
      current.map((item) => (item.rule_type === ruleType ? updater(item) : item)),
    );
  };

  if (loading) {
    return (
      <div className="thesis-shell p-6 flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="thesis-shell p-6 flex min-h-screen items-center justify-center">
        <Card className="thesis-panel w-full max-w-md border-white/10">
          <CardContent className="p-8 text-center">
            <Lock className="mx-auto mb-4 h-9 w-9 text-primary" />
            <h2 className="text-xl font-semibold text-foreground">Login required</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Trade-lab actions are private and only create simulated positions inside your account.
            </p>
            <Button className="mt-6" onClick={() => navigate('/auth')}>
              Continue to login
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const savePolicies = async () => {
    setSavingPolicies(true);
    try {
      const res = await thesisApi.upsertPolicies({ items: policyItems });
      setPolicyItems(toPolicyArray(res.effective));
      toast.success('Policy rules updated.');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Unable to save policy rules.');
    } finally {
      setSavingPolicies(false);
    }
  };

  const openTrade = async (event) => {
    event.preventDefault();
    setSubmittingTrade(true);
    setBlockedResult(null);
    try {
      const res = await thesisApi.openPaperTrade(thesisId, {
        side: tradeForm.side,
        size: Number(tradeForm.size),
        notes: tradeForm.notes.trim() || null,
      });
      setWorkspace((current) => ({
        ...current,
        paper_trades: [res.item, ...(current?.paper_trades || [])],
      }));
      setTradeForm((current) => ({ ...current, notes: '' }));
      toast.success('Paper trade opened.');
    } catch (err) {
      const policyResult = err.response?.data?.detail?.policy_result || null;
      setBlockedResult(policyResult);
      toast.error(err.response?.data?.detail?.message || 'Paper trade blocked.');
    } finally {
      setSubmittingTrade(false);
    }
  };

  const closeTrade = async (tradeId) => {
    try {
      const res = await thesisApi.updatePaperTrade(tradeId, { status: 'closed' });
      setWorkspace((current) => ({
        ...current,
        paper_trades: (current?.paper_trades || []).map((trade) =>
          trade.id === tradeId ? res.item : trade,
        ),
      }));
      toast.success('Paper trade closed.');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Unable to close trade.');
    }
  };

  return (
    <div className="thesis-shell min-h-screen p-4 md:p-6 lg:p-8" data-testid="thesis-trade-lab-page">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="thesis-kicker">Policy-constrained execution</div>
            <h1 className="thesis-display mt-2 text-4xl font-semibold text-foreground">
              {thesis?.ticker || 'Thesis'} <span className="text-primary">paper trade lab</span>
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted-foreground">
              This route is simulation-only. Every position is checked against typed risk rules before it is allowed into the paper portfolio.
            </p>
          </div>
          <Button asChild variant="outline" className="rounded-full border-white/10 bg-white/5 text-foreground hover:bg-white/10">
            <Link to={`/theses/${thesisId}`}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to thesis
            </Link>
          </Button>
        </div>

        {fetching ? (
          <Card className="thesis-panel rounded-[28px] border-white/10">
            <CardContent className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </CardContent>
          </Card>
        ) : (
          <>
            <Card className="thesis-panel rounded-[30px] border-white/10">
              <CardContent className="grid gap-4 p-6 md:grid-cols-3">
                <div className="rounded-[24px] border border-primary/20 bg-primary/10 p-4">
                  <div className="thesis-kicker">Simulated only</div>
                  <div className="mt-2 flex items-center gap-2 text-lg font-semibold text-foreground">
                    <ShieldCheck className="h-5 w-5 text-primary" />
                    No live broker routing
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">The lab can open and close paper trades only. Real execution is out of scope for this phase.</p>
                </div>
                <div className="rounded-[24px] border border-white/10 bg-white/5 p-4">
                  <div className="thesis-kicker">Evidence confidence</div>
                  <div className="mt-2 thesis-display text-3xl font-semibold text-foreground">
                    {avgConfidence === null ? '--' : `${avgConfidence.toFixed(0)}%`}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">Current average confidence across attached evidence blocks.</p>
                </div>
                <div className="rounded-[24px] border border-white/10 bg-white/5 p-4">
                  <div className="thesis-kicker">Trade count</div>
                  <div className="mt-2 thesis-display text-3xl font-semibold text-foreground">
                    {workspace?.paper_trades?.length || 0}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">Total simulated positions linked to this thesis lineage.</p>
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
              <Card className="thesis-panel rounded-[28px] border-white/10">
                <CardHeader>
                  <CardDescription className="thesis-kicker">Rule catalog</CardDescription>
                  <CardTitle className="text-2xl font-semibold text-foreground">Trading policies</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {policyItems.map((item) => {
                    const definition = POLICY_DEFS.find((entry) => entry.rule_type === item.rule_type);
                    if (!definition) return null;
                    return (
                      <div key={item.rule_type} className="rounded-[22px] border border-white/10 bg-white/5 p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <div className="font-medium text-foreground">{definition.label}</div>
                            <p className="mt-1 text-sm leading-6 text-muted-foreground">{definition.description}</p>
                          </div>
                          <Switch
                            checked={Boolean(item.enabled)}
                            onCheckedChange={(checked) =>
                              updatePolicy(item.rule_type, (current) => ({ ...current, enabled: checked }))
                            }
                          />
                        </div>
                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                          {definition.kind !== 'boolean' && (
                            <div className="space-y-2">
                              <label className="text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">
                                {definition.paramKey.replace(/_/g, ' ')}
                              </label>
                              <Input
                                type="number"
                                value={item.params?.[definition.paramKey] ?? ''}
                                onChange={(event) =>
                                  updatePolicy(item.rule_type, (current) => ({
                                    ...current,
                                    params: {
                                      ...current.params,
                                      [definition.paramKey]: Number(event.target.value),
                                    },
                                  }))
                                }
                                className="border-white/10 bg-black/20"
                              />
                            </div>
                          )}
                          {definition.secondaryKey && (
                            <div className="space-y-2">
                              <label className="text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">
                                {definition.secondaryKey.replace(/_/g, ' ')}
                              </label>
                              <Input
                                type="number"
                                value={item.params?.[definition.secondaryKey] ?? ''}
                                onChange={(event) =>
                                  updatePolicy(item.rule_type, (current) => ({
                                    ...current,
                                    params: {
                                      ...current.params,
                                      [definition.secondaryKey]: Number(event.target.value),
                                    },
                                  }))
                                }
                                className="border-white/10 bg-black/20"
                              />
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  <Button onClick={savePolicies} disabled={savingPolicies} className="rounded-full">
                    {savingPolicies ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Save policy rules
                  </Button>
                </CardContent>
              </Card>

              <div className="space-y-6">
                <Card className="thesis-panel rounded-[28px] border-white/10">
                  <CardHeader>
                    <CardDescription className="thesis-kicker">Open simulated position</CardDescription>
                    <CardTitle className="flex items-center gap-2 text-2xl font-semibold text-foreground">
                      <Beaker className="h-5 w-5 text-primary" />
                      Paper trade entry
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <form className="space-y-4" onSubmit={openTrade}>
                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                          <label className="text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">Side</label>
                          <Select
                            value={tradeForm.side}
                            onValueChange={(value) => setTradeForm((current) => ({ ...current, side: value }))}
                          >
                            <SelectTrigger className="border-white/10 bg-black/20">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="buy">Buy</SelectItem>
                              <SelectItem value="sell">Sell</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <label className="text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">Size</label>
                          <Input
                            type="number"
                            min="0"
                            step="0.01"
                            value={tradeForm.size}
                            onChange={(event) => setTradeForm((current) => ({ ...current, size: event.target.value }))}
                            className="border-white/10 bg-black/20"
                          />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <label className="text-xs font-mono uppercase tracking-[0.16em] text-muted-foreground">Notes</label>
                        <Textarea
                          value={tradeForm.notes}
                          onChange={(event) => setTradeForm((current) => ({ ...current, notes: event.target.value }))}
                          className="min-h-[110px] border-white/10 bg-black/20 text-sm leading-7"
                          placeholder="Why does the current evidence justify simulated entry right now?"
                        />
                      </div>

                      <div className="rounded-[22px] border border-white/10 bg-white/5 p-4 text-sm leading-6 text-muted-foreground">
                        Trade requests are evaluated against concentration, gross exposure, earnings-window, open-trade-count, and evidence-confidence rules.
                      </div>

                      <Button type="submit" disabled={submittingTrade} className="rounded-full">
                        {submittingTrade ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                        Open paper trade
                      </Button>
                    </form>
                  </CardContent>
                </Card>

                {blockedResult && (
                  <Card className="rounded-[28px] border border-destructive/30 bg-destructive/10">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-lg text-destructive">
                        <AlertTriangle className="h-5 w-5" />
                        Trade blocked
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      {(blockedResult.violations || []).map((failure, index) => (
                        <div key={`${failure.rule_type || 'failure'}-${index}`} className="rounded-2xl border border-destructive/30 bg-black/10 p-3 text-destructive">
                          <div className="font-medium">{failure.rule_type || 'policy'}</div>
                          <div className="mt-1">{failure.message}</div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                <Card className="thesis-panel rounded-[28px] border-white/10">
                  <CardHeader>
                    <CardDescription className="thesis-kicker">Trade journal</CardDescription>
                    <CardTitle className="text-2xl font-semibold text-foreground">Linked paper trades</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {(workspace?.paper_trades || []).length ? (
                      <div className="overflow-hidden rounded-[22px] border border-white/10 bg-white/5">
                        <Table>
                          <TableHeader className="bg-white/5">
                            <TableRow className="border-white/10">
                              <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em]">Trade</TableHead>
                              <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em]">Status</TableHead>
                              <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em]">Entry</TableHead>
                              <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em]">P&L</TableHead>
                              <TableHead className="text-right text-[11px] font-mono uppercase tracking-[0.16em]">Action</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {workspace.paper_trades.map((trade) => (
                              <TableRow key={trade.id} className="border-white/10">
                                <TableCell>
                                  <div className="font-medium text-foreground">{trade.side?.toUpperCase()} {trade.size} {trade.ticker}</div>
                                  <div className="mt-1 text-xs text-muted-foreground">{formatDate(trade.opened_at)}</div>
                                </TableCell>
                                <TableCell>
                                  <Badge variant="outline" className="border-white/10 bg-black/20 text-slate-200">
                                    {trade.status}
                                  </Badge>
                                </TableCell>
                                <TableCell className="text-sm text-muted-foreground">
                                  {formatMoney(trade.entry_price)}
                                </TableCell>
                                <TableCell className="text-sm text-muted-foreground">
                                  {trade.status === 'closed' ? (
                                    <span className={Number(trade.pnl || 0) >= 0 ? 'text-emerald-300' : 'text-red-300'}>
                                      {formatMoney(trade.pnl)}
                                    </span>
                                  ) : (
                                    '--'
                                  )}
                                </TableCell>
                                <TableCell className="text-right">
                                  {trade.status === 'open' ? (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => closeTrade(trade.id)}
                                      className="rounded-full border-amber-400/20 bg-amber-400/10 text-amber-200 hover:bg-amber-400/20"
                                    >
                                      Close trade
                                    </Button>
                                  ) : (
                                    <span className="text-xs text-muted-foreground">Closed {formatDate(trade.closed_at)}</span>
                                  )}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    ) : (
                      <div className="rounded-[22px] border border-dashed border-white/10 bg-white/5 p-5 text-sm text-muted-foreground">
                        No paper trades yet. Open one after the evidence and policy envelope line up.
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card className="thesis-panel rounded-[28px] border-white/10">
                  <CardHeader>
                    <CardDescription className="thesis-kicker">Context snapshot</CardDescription>
                    <CardTitle className="flex items-center gap-2 text-2xl font-semibold text-foreground">
                      <Target className="h-5 w-5 text-primary" />
                      Thesis context
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm leading-7 text-muted-foreground">
                    <p><span className="text-foreground">Claim:</span> {thesis?.claim}</p>
                    <p><span className="text-foreground">Why now:</span> {thesis?.why_now || '--'}</p>
                    <p><span className="text-foreground">Confidence:</span> {avgConfidence === null ? '--' : formatPercent(avgConfidence)}</p>
                    <div>
                      <div className="text-foreground">Invalidation</div>
                      <div className="mt-2 space-y-2">
                        {(thesis?.invalidation_conditions || []).map((condition, index) => (
                          <div key={`${condition}-${index}`} className="rounded-2xl border border-white/10 bg-black/20 px-3 py-2">
                            {condition}
                          </div>
                        ))}
                        {!thesis?.invalidation_conditions?.length && (
                          <div className="rounded-2xl border border-dashed border-white/10 bg-black/10 px-3 py-2 text-muted-foreground">
                            No invalidation conditions recorded.
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
