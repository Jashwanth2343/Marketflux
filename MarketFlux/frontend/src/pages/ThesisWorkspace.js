import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowRight,
  BookOpenText,
  ClipboardList,
  FileText,
  Loader2,
  Lock,
  Orbit,
  RefreshCw,
  Sparkles,
  Waypoints,
} from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '@/contexts/AuthContext';
import thesisApi from '@/lib/thesisApi';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const horizonOptions = [
  { value: 'short_term', label: 'Short term' },
  { value: 'medium_term', label: 'Medium term' },
  { value: 'long_term', label: 'Long term' },
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

function formatPercent(value) {
  if (value === null || value === undefined || value === '') return '--';
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return `${num.toFixed(0)}%`;
}

function formatFreshness(value) {
  if (value === null || value === undefined || value === '') return '--';
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return `${num.toFixed(0)}h`;
}

function policyClass(source) {
  const palette = {
    filing: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200',
    news: 'border-cyan-400/20 bg-cyan-400/10 text-cyan-200',
    macro: 'border-amber-400/20 bg-amber-400/10 text-amber-200',
    price_action: 'border-violet-400/20 bg-violet-400/10 text-violet-200',
    mirofish: 'border-pink-400/20 bg-pink-400/10 text-pink-200',
  };
  return palette[source] || 'border-white/10 bg-white/5 text-slate-200';
}

function getLinkItems(links) {
  if (Array.isArray(links)) return links;
  if (!links || typeof links !== 'object') return [];
  return Object.entries(links).map(([label, value]) => ({ label, value }));
}

function parseInvalidationConditions(text) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

function averageConfidence(evidenceBlocks) {
  if (!Array.isArray(evidenceBlocks) || evidenceBlocks.length === 0) return null;
  const nums = evidenceBlocks
    .map((item) => Number(item.confidence))
    .filter((value) => !Number.isNaN(value));
  if (nums.length === 0) return null;
  return nums.reduce((sum, value) => sum + value, 0) / nums.length;
}

export default function ThesisWorkspace() {
  const { thesisId } = useParams();
  const navigate = useNavigate();
  const { user, loading } = useAuth();
  const [workspace, setWorkspace] = useState(null);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState(null);
  const [revisionForm, setRevisionForm] = useState({
    claim: '',
    why_now: '',
    time_horizon: 'medium_term',
    status: 'active',
    invalidation_text: '',
    change_summary: '',
    auto_generate_summary: true,
  });
  const [memoDraft, setMemoDraft] = useState('');
  const [savingRevision, setSavingRevision] = useState(false);
  const [memoBusy, setMemoBusy] = useState(false);

  const loadWorkspace = useCallback(async ({ silent = false } = {}) => {
    if (!user) return;
    if (!silent) setFetching(true);
    try {
      const res = await thesisApi.getThesis(thesisId);
      const nextWorkspace = res.item;
      setWorkspace(nextWorkspace);
      setError(null);
      setRevisionForm({
        claim: nextWorkspace?.thesis?.claim || '',
        why_now: nextWorkspace?.thesis?.why_now || '',
        time_horizon: nextWorkspace?.thesis?.time_horizon || 'medium_term',
        status: nextWorkspace?.thesis?.status || 'active',
        invalidation_text: (nextWorkspace?.thesis?.invalidation_conditions || []).join('\n'),
        change_summary: '',
        auto_generate_summary: true,
      });
      setMemoDraft((current) => current || nextWorkspace?.memos?.[0]?.body || '');
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to load thesis workspace.');
    } finally {
      if (!silent) setFetching(false);
    }
  }, [thesisId, user]);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      setFetching(false);
      return;
    }
    loadWorkspace();
  }, [loading, user, loadWorkspace]);

  const groupedEvidence = useMemo(() => {
    if (!workspace?.evidence_groups) return [];
    return Object.entries(workspace.evidence_groups);
  }, [workspace]);

  const avgConfidence = useMemo(
    () => averageConfidence(workspace?.evidence_blocks || []),
    [workspace],
  );

  const latestRevision = workspace?.latest_revision;
  const thesis = workspace?.thesis;

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
              Thesis workspaces are private and require a signed-in session.
            </p>
            <Button className="mt-6" onClick={() => navigate('/auth')}>
              Continue to login
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const handleRevisionSubmit = async (event) => {
    event.preventDefault();
    setSavingRevision(true);
    try {
      const res = await thesisApi.reviseThesis(thesisId, {
        claim: revisionForm.claim.trim(),
        why_now: revisionForm.why_now.trim(),
        time_horizon: revisionForm.time_horizon,
        status: revisionForm.status,
        invalidation_conditions: parseInvalidationConditions(revisionForm.invalidation_text),
        change_summary: revisionForm.change_summary.trim() || null,
        auto_generate_summary: revisionForm.auto_generate_summary,
      });
      setWorkspace(res.item);
      setRevisionForm((current) => ({
        ...current,
        change_summary: '',
        invalidation_text: (res.item?.thesis?.invalidation_conditions || []).join('\n'),
      }));
      toast.success('Revision saved. Evidence refresh is running in the background.');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Unable to save revision.');
    } finally {
      setSavingRevision(false);
    }
  };

  const handleGenerateMemo = async () => {
    setMemoBusy(true);
    try {
      const res = await thesisApi.createMemo(thesisId, { mode: 'generate' });
      const nextMemo = res.item;
      setWorkspace((current) => ({
        ...current,
        memos: [nextMemo, ...(current?.memos || [])],
      }));
      setMemoDraft(nextMemo.body || '');
      toast.success('AI memo generated.');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Unable to generate memo.');
    } finally {
      setMemoBusy(false);
    }
  };

  const handleSaveMemo = async () => {
    if (!memoDraft.trim()) {
      toast.error('Write a memo body before saving.');
      return;
    }
    setMemoBusy(true);
    try {
      const res = await thesisApi.createMemo(thesisId, {
        mode: 'save',
        body: memoDraft,
      });
      setWorkspace((current) => ({
        ...current,
        memos: [res.item, ...(current?.memos || [])],
      }));
      toast.success('Memo saved.');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Unable to save memo.');
    } finally {
      setMemoBusy(false);
    }
  };

  return (
    <div className="thesis-shell min-h-screen p-4 md:p-6 lg:p-8" data-testid="thesis-workspace-page">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="thesis-kicker">Living thesis workspace</div>
            <h1 className="thesis-display mt-2 text-4xl font-semibold text-foreground">
              {thesis?.ticker || 'Thesis'} <span className="text-primary">workspace</span>
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-muted-foreground">
              Track the current claim, assess incoming evidence, generate memos, and decide whether the idea is strong enough for a policy-constrained paper trade.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              onClick={() => loadWorkspace()}
              className="rounded-full border-white/10 bg-white/5 text-foreground hover:bg-white/10"
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
            <Button asChild className="rounded-full">
              <Link to={`/theses/${thesisId}/trade-lab`}>
                Open paper trade lab
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>

        {fetching ? (
          <Card className="thesis-panel rounded-[28px] border-white/10">
            <CardContent className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </CardContent>
          </Card>
        ) : error ? (
          <Card className="thesis-panel rounded-[28px] border-destructive/30 bg-destructive/10">
            <CardContent className="p-6 text-sm text-destructive">{error}</CardContent>
          </Card>
        ) : (
          <>
            <Card className="thesis-panel overflow-hidden rounded-[32px] border-white/10">
              <CardContent className="relative p-6 md:p-8">
                <div className="absolute inset-y-0 right-0 hidden w-1/2 bg-[radial-gradient(circle_at_top_right,rgba(0,243,255,0.16),transparent_36%),radial-gradient(circle_at_bottom_right,rgba(255,176,0,0.1),transparent_32%)] lg:block" />
                <div className="relative grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
                  <div className="space-y-5">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="border-primary/20 bg-primary/10 text-primary">
                        {thesis?.status}
                      </Badge>
                      <Badge variant="outline" className="border-white/10 bg-white/5 text-slate-200">
                        {thesis?.time_horizon?.replace(/_/g, ' ')}
                      </Badge>
                      <Badge variant="outline" className="border-cyan-400/20 bg-cyan-400/10 text-cyan-200">
                        v{latestRevision?.version || 1}
                      </Badge>
                    </div>
                    <div>
                      <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                        <Orbit className="h-3.5 w-3.5 text-primary" />
                        Updated {formatDate(thesis?.updated_at)}
                      </div>
                      <h2 className="mt-4 text-2xl font-semibold leading-tight text-foreground md:text-3xl">
                        {thesis?.claim}
                      </h2>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-[24px] border border-white/10 bg-black/20 p-4">
                        <div className="thesis-kicker">Why now</div>
                        <p className="mt-3 text-sm leading-7 text-muted-foreground">
                          {thesis?.why_now || 'No why-now context has been captured yet.'}
                        </p>
                      </div>
                      <div className="rounded-[24px] border border-white/10 bg-black/20 p-4">
                        <div className="thesis-kicker">Invalidation conditions</div>
                        <div className="mt-3 space-y-2">
                          {(thesis?.invalidation_conditions || []).length ? (
                            thesis.invalidation_conditions.map((condition, index) => (
                              <div key={`${condition}-${index}`} className="rounded-2xl border border-amber-400/15 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
                                {condition}
                              </div>
                            ))
                          ) : (
                            <p className="text-sm text-muted-foreground">No invalidation conditions recorded yet.</p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                    <div className="thesis-metric p-4">
                      <div className="thesis-kicker">Evidence</div>
                      <div className="mt-2 thesis-display text-3xl font-semibold text-foreground">
                        {workspace?.evidence_blocks?.length || 0}
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">Typed blocks attached to this thesis.</p>
                    </div>
                    <div className="thesis-metric p-4">
                      <div className="thesis-kicker">Average confidence</div>
                      <div className="mt-2 thesis-display text-3xl font-semibold text-foreground">
                        {avgConfidence === null ? '--' : `${avgConfidence.toFixed(0)}%`}
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">Mean confidence across current evidence blocks.</p>
                    </div>
                    <div className="thesis-metric p-4">
                      <div className="thesis-kicker">Paper trades</div>
                      <div className="mt-2 thesis-display text-3xl font-semibold text-foreground">
                        {workspace?.paper_trades?.length || 0}
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">Linked simulated trades tied to this thesis lineage.</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Tabs defaultValue="overview" className="space-y-4">
              <TabsList className="h-auto flex-wrap justify-start gap-2 rounded-full bg-white/5 p-2">
                <TabsTrigger value="overview" className="rounded-full data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">Overview</TabsTrigger>
                <TabsTrigger value="evidence" className="rounded-full data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">Evidence</TabsTrigger>
                <TabsTrigger value="memos" className="rounded-full data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">Memos</TabsTrigger>
                <TabsTrigger value="revisions" className="rounded-full data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">Revisions</TabsTrigger>
              </TabsList>

              <TabsContent value="overview">
                <div className="grid gap-6 lg:grid-cols-[1fr_0.95fr]">
                  <Card className="thesis-panel rounded-[28px] border-white/10">
                    <CardHeader>
                      <CardDescription className="thesis-kicker">Current thesis</CardDescription>
                      <CardTitle className="text-2xl font-semibold text-foreground">Claim and context</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-5 text-sm leading-7 text-muted-foreground">
                      <div className="rounded-[24px] border border-white/10 bg-white/5 p-5">
                        <div className="flex items-center gap-2 text-foreground">
                          <BookOpenText className="h-4 w-4 text-primary" />
                          <span className="font-medium">Claim</span>
                        </div>
                        <p className="mt-3">{thesis?.claim}</p>
                      </div>
                      <div className="rounded-[24px] border border-white/10 bg-white/5 p-5">
                        <div className="flex items-center gap-2 text-foreground">
                          <Waypoints className="h-4 w-4 text-cyan-200" />
                          <span className="font-medium">Revision lineage</span>
                        </div>
                        <p className="mt-3">
                          The current thesis is on revision {latestRevision?.version || 1}. Every paper trade and memo can be tied back to this explicit snapshot.
                        </p>
                      </div>
                      <div className="rounded-[24px] border border-white/10 bg-white/5 p-5">
                        <div className="flex items-center gap-2 text-foreground">
                          <ClipboardList className="h-4 w-4 text-amber-200" />
                          <span className="font-medium">Current invalidation</span>
                        </div>
                        <div className="mt-3 space-y-2">
                          {(thesis?.invalidation_conditions || []).map((condition, index) => (
                            <div key={`${condition}-${index}`} className="rounded-2xl border border-white/10 bg-black/20 px-3 py-2">
                              {condition}
                            </div>
                          ))}
                          {!thesis?.invalidation_conditions?.length && (
                            <p>No invalidation conditions have been saved yet.</p>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <div className="space-y-6">
                    <Card className="thesis-panel rounded-[28px] border-white/10">
                      <CardHeader>
                        <CardDescription className="thesis-kicker">Fresh inputs</CardDescription>
                        <CardTitle className="text-2xl font-semibold text-foreground">Latest evidence</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {(workspace?.evidence_blocks || []).slice(0, 4).map((item) => (
                          <div key={item.id} className="rounded-[22px] border border-white/10 bg-white/5 p-4">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant="outline" className={policyClass(item.source)}>
                                {String(item.source || 'unknown').replace(/_/g, ' ')}
                              </Badge>
                              <span className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
                                {formatDate(item.observed_at || item.created_at)}
                              </span>
                            </div>
                            <p className="mt-3 text-sm leading-6 text-foreground">{item.summary}</p>
                          </div>
                        ))}
                        {!workspace?.evidence_blocks?.length && (
                          <div className="rounded-[22px] border border-dashed border-white/10 bg-white/5 p-5 text-sm text-muted-foreground">
                            No evidence blocks yet. The background collectors may still be running.
                          </div>
                        )}
                      </CardContent>
                    </Card>

                    <Card className="thesis-panel rounded-[28px] border-white/10">
                      <CardHeader>
                        <CardDescription className="thesis-kicker">Execution context</CardDescription>
                        <CardTitle className="text-2xl font-semibold text-foreground">Linked paper trades</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {(workspace?.paper_trades || []).slice(0, 3).map((trade) => (
                          <div key={trade.id} className="rounded-[22px] border border-white/10 bg-white/5 p-4">
                            <div className="flex items-center justify-between gap-3">
                              <div className="font-medium text-foreground">
                                {trade.side?.toUpperCase()} {trade.size} {trade.ticker}
                              </div>
                              <Badge variant="outline" className="border-white/10 bg-black/20 text-slate-200">
                                {trade.status}
                              </Badge>
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground">
                              Opened {formatDate(trade.opened_at)} at ${Number(trade.entry_price || 0).toFixed(2)}
                            </p>
                          </div>
                        ))}
                        {!workspace?.paper_trades?.length && (
                          <div className="rounded-[22px] border border-dashed border-white/10 bg-white/5 p-5 text-sm text-muted-foreground">
                            No paper trades linked yet. Open the trade lab when the thesis is ready for simulated execution.
                          </div>
                        )}
                        <Button asChild variant="outline" className="w-full rounded-full border-primary/20 bg-primary/10 text-primary hover:bg-primary/20">
                          <Link to={`/theses/${thesisId}/trade-lab`}>Go to paper trade lab</Link>
                        </Button>
                      </CardContent>
                    </Card>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="evidence">
                <Card className="thesis-panel rounded-[28px] border-white/10">
                  <CardHeader>
                    <CardDescription className="thesis-kicker">Typed evidence</CardDescription>
                    <CardTitle className="text-2xl font-semibold text-foreground">Evidence panel</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {groupedEvidence.length ? (
                      groupedEvidence.map(([source, items]) => (
                        <div key={source} className="space-y-4">
                          <div className="flex items-center gap-3">
                            <Badge variant="outline" className={policyClass(source)}>
                              {source.replace(/_/g, ' ')}
                            </Badge>
                            <span className="text-sm text-muted-foreground">{items.length} block{items.length === 1 ? '' : 's'}</span>
                          </div>
                          <div className="grid gap-4 lg:grid-cols-2">
                            {items.map((item) => (
                              <Card key={item.id} className="rounded-[24px] border-white/10 bg-white/5 shadow-none">
                                <CardContent className="p-5">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <Badge variant="outline" className={policyClass(item.source)}>
                                      {String(item.source || 'unknown').replace(/_/g, ' ')}
                                    </Badge>
                                    <span className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
                                      confidence {formatPercent(item.confidence)}
                                    </span>
                                    <span className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
                                      freshness {formatFreshness(item.freshness)}
                                    </span>
                                  </div>
                                  <p className="mt-4 text-sm leading-7 text-foreground">{item.summary}</p>
                                  <Separator className="my-4 bg-white/10" />
                                  <div className="space-y-2">
                                    {getLinkItems(item.links).length ? (
                                      getLinkItems(item.links).map((link, index) => {
                                        const href = typeof link === 'string' ? link : link.value;
                                        const label = typeof link === 'string' ? link : link.label;
                                        if (!href) return null;
                                        return (
                                          <a
                                            key={`${item.id}-link-${index}`}
                                            href={href}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="block text-sm text-primary transition-colors hover:text-primary/80"
                                          >
                                            {label || href}
                                          </a>
                                        );
                                      })
                                    ) : (
                                      <p className="text-sm text-muted-foreground">No external links attached.</p>
                                    )}
                                  </div>
                                </CardContent>
                              </Card>
                            ))}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[24px] border border-dashed border-white/10 bg-white/5 p-8 text-center text-sm text-muted-foreground">
                        Evidence blocks will appear here after the background collectors finish.
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="memos">
                <div className="grid gap-6 lg:grid-cols-[1fr_0.95fr]">
                  <Card className="thesis-panel rounded-[28px] border-white/10">
                    <CardHeader>
                      <CardDescription className="thesis-kicker">Memo generator</CardDescription>
                      <CardTitle className="flex items-center gap-2 text-2xl font-semibold text-foreground">
                        <Sparkles className="h-5 w-5 text-primary" />
                        Summarize the thesis
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="rounded-[22px] border border-white/10 bg-white/5 p-4 text-sm leading-7 text-muted-foreground">
                        Generate an AI memo from the latest revision and current evidence, or write your own manual memo and save it as a durable artifact.
                      </div>
                      <Textarea
                        value={memoDraft}
                        onChange={(event) => setMemoDraft(event.target.value)}
                        placeholder="Write your analyst memo here, or generate one from the latest thesis context."
                        className="min-h-[260px] border-white/10 bg-black/20 text-sm leading-7"
                      />
                      <div className="flex flex-wrap gap-3">
                        <Button onClick={handleGenerateMemo} disabled={memoBusy} className="rounded-full">
                          {memoBusy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                          Generate AI memo
                        </Button>
                        <Button
                          variant="outline"
                          onClick={handleSaveMemo}
                          disabled={memoBusy}
                          className="rounded-full border-white/10 bg-white/5 text-foreground hover:bg-white/10"
                        >
                          Save memo draft
                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="thesis-panel rounded-[28px] border-white/10">
                    <CardHeader>
                      <CardDescription className="thesis-kicker">Memo archive</CardDescription>
                      <CardTitle className="text-2xl font-semibold text-foreground">Linked memos</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {(workspace?.memos || []).length ? (
                        workspace.memos.map((memo) => (
                          <div key={memo.id} className="rounded-[22px] border border-white/10 bg-white/5 p-5">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div>
                                <div className="font-medium text-foreground">{memo.summary || 'Untitled memo'}</div>
                                <div className="mt-1 text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
                                  {memo.generated_by} • {formatDate(memo.created_at)}
                                </div>
                              </div>
                              <Badge variant="outline" className="border-white/10 bg-black/20 text-slate-200">
                                revision {memo.revision_id ? 'linked' : 'n/a'}
                              </Badge>
                            </div>
                            <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-muted-foreground">{memo.body}</p>
                          </div>
                        ))
                      ) : (
                        <div className="rounded-[22px] border border-dashed border-white/10 bg-white/5 p-5 text-sm text-muted-foreground">
                          No memos yet. Generate one after the first evidence blocks land.
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              <TabsContent value="revisions">
                <div className="grid gap-6 lg:grid-cols-[1fr_0.95fr]">
                  <Card className="thesis-panel rounded-[28px] border-white/10">
                    <CardHeader>
                      <CardDescription className="thesis-kicker">Revision editor</CardDescription>
                      <CardTitle className="text-2xl font-semibold text-foreground">Revise thesis</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <form className="space-y-4" onSubmit={handleRevisionSubmit}>
                        <div className="space-y-2">
                          <label className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground">Claim</label>
                          <Textarea
                            value={revisionForm.claim}
                            onChange={(event) => setRevisionForm((current) => ({ ...current, claim: event.target.value }))}
                            className="min-h-[140px] border-white/10 bg-black/20 text-sm leading-7"
                          />
                        </div>

                        <div className="space-y-2">
                          <label className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground">Why now</label>
                          <Textarea
                            value={revisionForm.why_now}
                            onChange={(event) => setRevisionForm((current) => ({ ...current, why_now: event.target.value }))}
                            className="min-h-[120px] border-white/10 bg-black/20 text-sm leading-7"
                          />
                        </div>

                        <div className="grid gap-4 md:grid-cols-2">
                          <div className="space-y-2">
                            <label className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground">Time horizon</label>
                            <Select
                              value={revisionForm.time_horizon}
                              onValueChange={(value) => setRevisionForm((current) => ({ ...current, time_horizon: value }))}
                            >
                              <SelectTrigger className="border-white/10 bg-black/20">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {horizonOptions.map((option) => (
                                  <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-2">
                            <label className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground">Status</label>
                            <Select
                              value={revisionForm.status}
                              onValueChange={(value) => setRevisionForm((current) => ({ ...current, status: value }))}
                            >
                              <SelectTrigger className="border-white/10 bg-black/20">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="active">Active</SelectItem>
                                <SelectItem value="retired">Retired</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <label className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground">Invalidation conditions</label>
                          <Textarea
                            value={revisionForm.invalidation_text}
                            onChange={(event) => setRevisionForm((current) => ({ ...current, invalidation_text: event.target.value }))}
                            className="min-h-[120px] border-white/10 bg-black/20 text-sm leading-7"
                          />
                        </div>

                        <div className="space-y-2">
                          <label className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground">Manual change summary</label>
                          <Input
                            value={revisionForm.change_summary}
                            onChange={(event) => setRevisionForm((current) => ({ ...current, change_summary: event.target.value }))}
                            placeholder="Optional. Leave blank to let AI summarize the diff."
                            className="border-white/10 bg-black/20"
                          />
                        </div>

                        <div className="rounded-[22px] border border-white/10 bg-white/5 p-4 text-sm text-muted-foreground">
                          Saving a revision updates the canonical thesis, writes an immutable snapshot, and queues another evidence refresh in the background.
                        </div>

                        <Button type="submit" disabled={savingRevision} className="rounded-full">
                          {savingRevision ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                          Save revision
                        </Button>
                      </form>
                    </CardContent>
                  </Card>

                  <Card className="thesis-panel rounded-[28px] border-white/10">
                    <CardHeader>
                      <CardDescription className="thesis-kicker">Timeline</CardDescription>
                      <CardTitle className="text-2xl font-semibold text-foreground">Revision history</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {(workspace?.revisions || []).map((revision) => (
                        <div key={revision.id} className="rounded-[22px] border border-white/10 bg-white/5 p-5">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="border-cyan-400/20 bg-cyan-400/10 text-cyan-200">
                                v{revision.version}
                              </Badge>
                              <span className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
                                {formatDate(revision.created_at)}
                              </span>
                            </div>
                            <Badge variant="outline" className="border-white/10 bg-black/20 text-slate-200">
                              {revision.status}
                            </Badge>
                          </div>
                          <p className="mt-4 text-sm leading-7 text-foreground">{revision.change_summary || 'No change summary captured.'}</p>
                          <Separator className="my-4 bg-white/10" />
                          <div className="space-y-2 text-sm text-muted-foreground">
                            <div><span className="text-foreground">Claim:</span> {revision.claim}</div>
                            <div><span className="text-foreground">Why now:</span> {revision.why_now || '--'}</div>
                            <div><span className="text-foreground">Horizon:</span> {revision.time_horizon?.replace(/_/g, ' ')}</div>
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>
            </Tabs>
          </>
        )}
      </div>
    </div>
  );
}
