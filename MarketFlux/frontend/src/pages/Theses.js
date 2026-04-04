import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  BookOpenText,
  FileText,
  FlaskConical,
  Loader2,
  Lock,
  Orbit,
  Sparkles,
} from 'lucide-react';

import { useAuth } from '@/contexts/AuthContext';
import thesisApi from '@/lib/thesisApi';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

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

function statusTone(status) {
  if (status === 'active') return 'text-emerald-300 border-emerald-400/20 bg-emerald-400/10';
  if (status === 'retired') return 'text-amber-200 border-amber-400/20 bg-amber-400/10';
  return 'text-slate-200 border-white/10 bg-white/5';
}

export default function Theses() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (loading || !user) {
      setFetching(false);
      return;
    }

    let active = true;
    const run = async () => {
      setFetching(true);
      try {
        const res = await thesisApi.listTheses();
        if (active) {
          setItems(res.items || []);
          setError(null);
        }
      } catch (err) {
        if (active) {
          setError(err.response?.data?.detail || 'Unable to load theses right now.');
        }
      } finally {
        if (active) setFetching(false);
      }
    };

    run();
    return () => {
      active = false;
    };
  }, [loading, user]);

  const stats = useMemo(() => {
    const activeCount = items.filter((item) => item.status === 'active').length;
    const openTrades = items.reduce((sum, item) => sum + Number(item.open_trade_count || 0), 0);
    const evidenceCount = items.reduce((sum, item) => sum + Number(item.evidence_count || 0), 0);
    return { activeCount, openTrades, evidenceCount };
  }, [items]);

  if (loading) {
    return (
      <div className="thesis-shell p-6 flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="thesis-shell p-6 flex min-h-screen items-center justify-center" data-testid="theses-page">
        <Card className="thesis-panel w-full max-w-md border-white/10">
          <CardContent className="p-8 text-center">
            <Lock className="mx-auto mb-4 h-9 w-9 text-primary" />
            <h2 className="text-xl font-semibold text-foreground">Login required</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Thesis workspaces, memos, and paper trades are private to your account.
            </p>
            <Button className="mt-6" onClick={() => navigate('/auth')}>
              Continue to login
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="thesis-shell min-h-screen p-4 md:p-6 lg:p-8" data-testid="theses-page">
      <div className="mx-auto max-w-7xl space-y-6">
        <Card className="thesis-panel overflow-hidden rounded-[32px] border-white/10">
          <CardContent className="relative p-6 md:p-8 lg:p-10">
            <div className="absolute inset-y-0 right-0 hidden w-1/2 bg-[radial-gradient(circle_at_top_right,rgba(0,243,255,0.18),transparent_42%),radial-gradient(circle_at_bottom,rgba(255,176,0,0.12),transparent_35%)] lg:block" />
            <div className="relative grid gap-6 lg:grid-cols-[1.35fr_0.65fr] lg:items-end">
              <div className="space-y-5">
                <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[11px] font-mono uppercase tracking-[0.2em] text-primary">
                  <Orbit className="h-3.5 w-3.5" />
                  Thesis OS
                </div>
                <div>
                  <h1 className="thesis-display max-w-4xl text-4xl font-semibold leading-[1.02] text-foreground md:text-5xl">
                    Living investment theses with evidence, memos, and safe paper execution.
                  </h1>
                  <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground md:text-base">
                    Create a claim, attach explainable evidence blocks, revise with intent, and route every simulated trade through explicit policy checks.
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Button onClick={() => navigate('/theses/new')} className="h-11 rounded-full px-6 text-sm font-semibold">
                    Create thesis
                  </Button>
                  <Button variant="outline" onClick={() => navigate('/portfolio')} className="h-11 rounded-full border-white/10 bg-white/5 px-6 text-sm font-semibold text-foreground hover:bg-white/10">
                    Review portfolio context
                  </Button>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                <div className="thesis-metric p-4">
                  <div className="thesis-kicker">Active theses</div>
                  <div className="mt-2 thesis-display text-3xl font-semibold text-foreground">{stats.activeCount}</div>
                  <p className="mt-1 text-sm text-muted-foreground">Claims currently being tracked.</p>
                </div>
                <div className="thesis-metric p-4">
                  <div className="thesis-kicker">Evidence blocks</div>
                  <div className="mt-2 thesis-display text-3xl font-semibold text-foreground">{stats.evidenceCount}</div>
                  <p className="mt-1 text-sm text-muted-foreground">Structured inputs across filing, news, macro, and price action.</p>
                </div>
                <div className="thesis-metric p-4">
                  <div className="thesis-kicker">Open paper trades</div>
                  <div className="mt-2 thesis-display text-3xl font-semibold text-foreground">{stats.openTrades}</div>
                  <p className="mt-1 text-sm text-muted-foreground">Every position stays simulated by default.</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 md:grid-cols-3">
          <Card className="thesis-panel border-white/10">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <BookOpenText className="h-4 w-4 text-primary" />
                Explicit claims
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 text-sm leading-6 text-muted-foreground">
              Track the thesis, time horizon, why-now context, and invalidation conditions in one durable object.
            </CardContent>
          </Card>
          <Card className="thesis-panel border-white/10">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="h-4 w-4 text-cyan-300" />
                AI memo loop
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 text-sm leading-6 text-muted-foreground">
              Generate explainable memos from the latest thesis revision and supporting evidence, then edit and save them.
            </CardContent>
          </Card>
          <Card className="thesis-panel border-white/10">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <FlaskConical className="h-4 w-4 text-amber-300" />
                Safe paper trading
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 text-sm leading-6 text-muted-foreground">
              Run simulated positions through typed policies first, including exposure, confidence, and earnings-window guardrails.
            </CardContent>
          </Card>
        </div>

        <Card className="thesis-panel rounded-[28px] border-white/10">
          <CardHeader className="pb-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardDescription className="thesis-kicker">Workspace index</CardDescription>
                <CardTitle className="thesis-display mt-2 text-3xl font-semibold text-foreground">Your thesis library</CardTitle>
              </div>
              <Button variant="outline" onClick={() => navigate('/theses/new')} className="rounded-full border-primary/20 bg-primary/10 text-primary hover:bg-primary/20">
                New thesis
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {fetching ? (
              <div className="flex h-40 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : error ? (
              <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                {error}
              </div>
            ) : items.length === 0 ? (
              <div className="rounded-[24px] border border-dashed border-white/10 bg-white/5 p-8 text-center">
                <FileText className="mx-auto h-8 w-8 text-primary" />
                <h2 className="mt-4 text-xl font-semibold text-foreground">No theses yet</h2>
                <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
                  Start with a single ticker, define the claim, and let MarketFlux collect the first round of evidence blocks in the background.
                </p>
                <Button className="mt-6" onClick={() => navigate('/theses/new')}>
                  Create your first thesis
                </Button>
              </div>
            ) : (
              <div className="overflow-hidden rounded-[24px] border border-white/10 bg-white/5">
                <Table>
                  <TableHeader className="bg-white/5">
                    <TableRow className="border-white/10">
                      <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em]">Ticker</TableHead>
                      <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em]">Claim</TableHead>
                      <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em]">Status</TableHead>
                      <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em]">Horizon</TableHead>
                      <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em]">Signals</TableHead>
                      <TableHead className="text-[11px] font-mono uppercase tracking-[0.16em]">Updated</TableHead>
                      <TableHead className="text-right text-[11px] font-mono uppercase tracking-[0.16em]">Open</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((item) => (
                      <TableRow key={item.id} className="border-white/10">
                        <TableCell className="font-mono text-sm text-foreground">{item.ticker}</TableCell>
                        <TableCell>
                          <div className="max-w-[420px]">
                            <div className="line-clamp-2 font-medium text-foreground">{item.claim}</div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              Revision v{item.latest_revision_version || 1}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className={statusTone(item.status)}>
                            {item.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">{item.time_horizon?.replace(/_/g, ' ')}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-2">
                            <Badge variant="outline" className="border-cyan-400/20 bg-cyan-400/10 text-cyan-200">
                              {item.evidence_count || 0} evidence
                            </Badge>
                            <Badge variant="outline" className="border-amber-400/20 bg-amber-400/10 text-amber-200">
                              {item.open_trade_count || 0} open trades
                            </Badge>
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">{formatDate(item.updated_at)}</TableCell>
                        <TableCell className="text-right">
                          <Button asChild variant="ghost" className="rounded-full text-primary hover:bg-primary/10 hover:text-primary">
                            <Link to={`/theses/${item.id}`}>
                              Open
                              <ArrowRight className="ml-2 h-4 w-4" />
                            </Link>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
