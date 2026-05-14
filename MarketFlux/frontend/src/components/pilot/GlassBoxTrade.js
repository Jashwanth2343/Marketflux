import { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Loader2,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  FileText,
  MessageSquare,
  BarChart2,
  GitBranch,
  ClipboardList,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as ReTooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { AdversarialDebate } from '@/components/pilot/AdversarialDebate';

const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

function formatDate(value) {
  if (!value) return '--';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
}

function formatCurrency(value) {
  if (value === null || value === undefined || value === '') return '--';
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

function JsonNode({ value, depth = 0 }) {
  if (value === null) return <span className="text-muted-foreground">null</span>;
  if (typeof value === 'boolean') {
    return <span className={value ? 'text-green-500' : 'text-red-500'}>{String(value)}</span>;
  }
  if (typeof value === 'number') {
    return <span className="text-amber-400 font-mono">{value}</span>;
  }
  if (typeof value === 'string') {
    return <span className="text-cyan-400">"{value}"</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-muted-foreground">[]</span>;
    return (
      <div className="pl-3 border-l border-border/60 ml-1">
        {value.map((v, idx) => (
          <div key={idx} className="text-xs font-mono">
            <span className="text-muted-foreground">[{idx}]</span>{' '}
            <JsonNode value={v} depth={depth + 1} />
          </div>
        ))}
      </div>
    );
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value);
    if (entries.length === 0) return <span className="text-muted-foreground">{'{}'}</span>;
    return (
      <div className={depth === 0 ? '' : 'pl-3 border-l border-border/60 ml-1'}>
        {entries.map(([k, v]) => (
          <div key={k} className="text-xs font-mono break-words">
            <span className="text-primary">{k}</span>
            <span className="text-muted-foreground">: </span>
            <JsonNode value={v} depth={depth + 1} />
          </div>
        ))}
      </div>
    );
  }
  return <span className="text-foreground">{String(value)}</span>;
}

function ThesisTab({ proposal }) {
  if (!proposal) return null;
  return (
    <div className="space-y-4">
      <div className="bg-card border border-border rounded-lg p-4">
        <div className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-2">
          Thesis
        </div>
        <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
          {proposal.thesis || 'No thesis provided.'}
        </p>
      </div>

      {proposal.invalidation ? (
        <div className="bg-red-500/5 border border-red-500/30 rounded-lg p-4">
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-red-400 mb-2">
            <AlertTriangle className="w-3 h-3" />
            Invalidation
          </div>
          <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
            {proposal.invalidation}
          </p>
        </div>
      ) : null}

      {proposal.dissent_summary ? (
        <div className="bg-amber-500/5 border border-amber-500/30 rounded-lg p-4">
          <div className="text-xs font-mono uppercase tracking-wider text-amber-400 mb-2">
            Dissent summary
          </div>
          <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
            {proposal.dissent_summary}
          </p>
        </div>
      ) : null}

      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="text-left text-[10px] font-mono uppercase tracking-wider text-muted-foreground px-3 py-2">
                Field
              </th>
              <th className="text-right text-[10px] font-mono uppercase tracking-wider text-muted-foreground px-3 py-2">
                Value
              </th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-border">
              <td className="px-3 py-2 text-muted-foreground">Side</td>
              <td className="px-3 py-2 text-right font-mono uppercase">
                {proposal.side || '--'}
              </td>
            </tr>
            <tr className="border-t border-border">
              <td className="px-3 py-2 text-muted-foreground">Quantity</td>
              <td className="px-3 py-2 text-right font-mono">{proposal.qty ?? '--'}</td>
            </tr>
            <tr className="border-t border-border">
              <td className="px-3 py-2 text-muted-foreground">Quote price</td>
              <td className="px-3 py-2 text-right font-mono">
                {formatCurrency(proposal.quote_price)}
              </td>
            </tr>
            <tr className="border-t border-border">
              <td className="px-3 py-2 text-muted-foreground">Notional</td>
              <td className="px-3 py-2 text-right font-mono">
                {formatCurrency(proposal.proposed_notional)}
              </td>
            </tr>
            <tr className="border-t border-border">
              <td className="px-3 py-2 text-muted-foreground">Stop loss</td>
              <td className="px-3 py-2 text-right font-mono text-red-400">
                {formatCurrency(proposal.stop_loss_price)}
              </td>
            </tr>
            <tr className="border-t border-border">
              <td className="px-3 py-2 text-muted-foreground">Take profit</td>
              <td className="px-3 py-2 text-right font-mono text-green-500">
                {formatCurrency(proposal.take_profit_price)}
              </td>
            </tr>
            <tr className="border-t border-border">
              <td className="px-3 py-2 text-muted-foreground">Conviction</td>
              <td className="px-3 py-2 text-right font-mono">
                {proposal.conviction != null ? `${proposal.conviction}/10` : '--'}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SignalsTab({ signal }) {
  if (!signal) {
    return (
      <div className="text-sm text-muted-foreground">No signal snapshot available.</div>
    );
  }
  const categories = signal.categories;
  const categoryData =
    categories && typeof categories === 'object'
      ? Object.entries(categories)
          .filter(([, v]) => typeof v === 'number' || (v && typeof v.score === 'number'))
          .map(([k, v]) => ({
            name: k,
            score: typeof v === 'number' ? v : Number(v.score) || 0,
          }))
      : [];

  return (
    <div className="space-y-4">
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <tbody>
            {Object.entries(signal).map(([k, v]) => {
              if (k === 'categories') return null;
              const display =
                typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v ?? '--');
              return (
                <tr key={k} className="border-b border-border last:border-b-0">
                  <td className="px-3 py-2 text-muted-foreground font-mono text-xs uppercase tracking-wider w-1/2">
                    {k}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs break-all">{display}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {categoryData.length ? (
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-3">
            Category scores
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryData} layout="vertical" margin={{ left: 8, right: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                <XAxis type="number" stroke="#888" fontSize={10} />
                <YAxis
                  type="category"
                  dataKey="name"
                  stroke="#888"
                  fontSize={10}
                  width={100}
                />
                <ReTooltip
                  contentStyle={{
                    background: '#111',
                    border: '1px solid #333',
                    fontSize: 11,
                  }}
                />
                <Bar dataKey="score" fill="#22c55e" radius={[2, 2, 2, 2]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function PolicyTab({ policy }) {
  if (!policy) {
    return (
      <div className="text-sm text-muted-foreground">No policy verdict available.</div>
    );
  }
  const violations = Array.isArray(policy.violations) ? policy.violations : [];
  const warnings = Array.isArray(policy.warnings) ? policy.warnings : [];

  return (
    <div className="space-y-4">
      <div
        className={`flex items-center gap-2 p-3 rounded-lg border ${
          policy.allowed
            ? 'bg-green-500/10 border-green-500/30 text-green-500'
            : 'bg-red-500/10 border-red-500/30 text-red-500'
        }`}
      >
        {policy.allowed ? <ShieldCheck className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
        <span className="text-sm font-mono uppercase tracking-wider">
          {policy.allowed ? 'Allowed by policy' : 'Blocked by policy'}
        </span>
      </div>

      {violations.length ? (
        <div className="space-y-2">
          <div className="text-xs font-mono uppercase tracking-wider text-red-400">
            Violations
          </div>
          {violations.map((v, idx) => (
            <div
              key={idx}
              className="bg-red-500/5 border border-red-500/30 rounded-lg p-3 text-sm"
            >
              <div className="text-[10px] font-mono uppercase tracking-wider text-red-400 mb-1">
                {v.rule_type || 'rule'}
              </div>
              <div className="text-foreground/90">{v.message || JSON.stringify(v)}</div>
            </div>
          ))}
        </div>
      ) : null}

      {warnings.length ? (
        <div className="space-y-2">
          <div className="text-xs font-mono uppercase tracking-wider text-amber-400">
            Warnings
          </div>
          {warnings.map((w, idx) => (
            <div
              key={idx}
              className="bg-amber-500/5 border border-amber-500/30 rounded-lg p-3 text-sm text-foreground/90"
            >
              {typeof w === 'string' ? w : JSON.stringify(w)}
            </div>
          ))}
        </div>
      ) : null}

      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <tbody>
            {Object.entries(policy)
              .filter(([k]) => !['violations', 'warnings'].includes(k))
              .map(([k, v]) => (
                <tr key={k} className="border-b border-border last:border-b-0">
                  <td className="px-3 py-2 text-muted-foreground font-mono text-xs uppercase tracking-wider w-1/2">
                    {k}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs break-all">
                    {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '--')}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CatalystTab({ catalyst }) {
  if (!catalyst) {
    return (
      <div className="bg-muted/40 border border-border rounded-lg p-4 text-sm text-muted-foreground">
        Not earnings-adjacent — no stress test run.
      </div>
    );
  }
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <JsonNode value={catalyst} />
    </div>
  );
}

function AuditTab({ audit }) {
  if (!Array.isArray(audit) || audit.length === 0) {
    return <div className="text-sm text-muted-foreground">No audit events yet.</div>;
  }
  return (
    <div className="space-y-2">
      {audit.map((evt, idx) => (
        <div
          key={evt?.id || idx}
          className="bg-card border border-border rounded-lg p-3 text-sm"
        >
          <div className="flex items-center justify-between gap-2 mb-1">
            <div className="text-xs font-mono uppercase tracking-wider text-primary">
              {evt?.event_type || evt?.type || 'event'}
            </div>
            <div className="text-[10px] font-mono text-muted-foreground">
              {formatDate(evt?.timestamp || evt?.created_at)}
            </div>
          </div>
          <div className="text-foreground/90 text-sm">
            {evt?.message || (evt?.payload ? JSON.stringify(evt.payload) : '')}
          </div>
        </div>
      ))}
    </div>
  );
}

export function GlassBoxTrade({ open, onOpenChange, proposalId, initialProposal }) {
  const [proposal, setProposal] = useState(initialProposal || null);
  const [audit, setAudit] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !proposalId) return undefined;
    let active = true;
    setLoading(true);
    const run = async () => {
      try {
        const res = await axios.get(`${API}/api/pilot/proposals/${proposalId}`, {
          withCredentials: true,
        });
        if (!active) return;
        setProposal(res?.data?.item || initialProposal || null);
        setAudit(Array.isArray(res?.data?.audit) ? res.data.audit : []);
      } catch (err) {
        if (!active) return;
        const detail =
          err?.response?.data?.detail || err?.response?.data?.message || err?.message || 'error';
        toast.error(`Could not load proposal details. Backend says: ${String(detail)}`);
      } finally {
        if (active) setLoading(false);
      }
    };
    run();
    return () => {
      active = false;
    };
  }, [open, proposalId, initialProposal]);

  const transcript = proposal?.debate_transcript || [];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-2xl lg:max-w-3xl overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-primary" />
            {proposal
              ? `${(proposal.side || '').toUpperCase()} ${proposal.qty || ''} ${proposal.ticker || ''}`
              : 'Trade detail'}
          </SheetTitle>
          <SheetDescription>
            {proposal?.personality_name ? `Proposed by ${proposal.personality_name}` : ''}
            {proposal?.created_at ? ` · ${formatDate(proposal.created_at)}` : ''}
          </SheetDescription>
        </SheetHeader>

        {loading && !proposal ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
          </div>
        ) : null}

        {proposal ? (
          <div className="mt-4 flex items-center gap-2 flex-wrap">
            <Badge variant="outline" className="font-mono uppercase tracking-wider">
              {proposal.status || 'pending'}
            </Badge>
            {proposal.conviction != null ? (
              <Badge variant="outline" className="font-mono">
                Conviction {proposal.conviction}/10
              </Badge>
            ) : null}
            {proposal.signal_snapshot?.signal_label ? (
              <Badge variant="outline" className="font-mono">
                {proposal.signal_snapshot.signal_label}
              </Badge>
            ) : null}
          </div>
        ) : null}

        <Tabs defaultValue="thesis" className="mt-4">
          <TabsList className="w-full flex flex-wrap h-auto justify-start gap-1 bg-muted/40">
            <TabsTrigger value="thesis" className="gap-1 text-xs">
              <FileText className="w-3 h-3" /> Thesis
            </TabsTrigger>
            <TabsTrigger value="debate" className="gap-1 text-xs">
              <MessageSquare className="w-3 h-3" /> Debate
            </TabsTrigger>
            <TabsTrigger value="signals" className="gap-1 text-xs">
              <BarChart2 className="w-3 h-3" /> Signals
            </TabsTrigger>
            <TabsTrigger value="risk" className="gap-1 text-xs">
              <ShieldAlert className="w-3 h-3" /> Risk
            </TabsTrigger>
            <TabsTrigger value="policy" className="gap-1 text-xs">
              <ShieldCheck className="w-3 h-3" /> Policy
            </TabsTrigger>
            <TabsTrigger value="catalyst" className="gap-1 text-xs">
              <GitBranch className="w-3 h-3" /> Catalyst
            </TabsTrigger>
            <TabsTrigger value="audit" className="gap-1 text-xs">
              <ClipboardList className="w-3 h-3" /> Audit
            </TabsTrigger>
          </TabsList>

          <TabsContent value="thesis" className="mt-4">
            <ThesisTab proposal={proposal} />
          </TabsContent>
          <TabsContent value="debate" className="mt-4">
            <AdversarialDebate transcript={transcript} />
          </TabsContent>
          <TabsContent value="signals" className="mt-4">
            <SignalsTab signal={proposal?.signal_snapshot} />
          </TabsContent>
          <TabsContent value="risk" className="mt-4">
            <div className="bg-card border border-border rounded-lg p-4 overflow-auto">
              {proposal?.risk_verdict ? (
                <JsonNode value={proposal.risk_verdict} />
              ) : (
                <div className="text-sm text-muted-foreground">No risk verdict recorded.</div>
              )}
            </div>
          </TabsContent>
          <TabsContent value="policy" className="mt-4">
            <PolicyTab policy={proposal?.policy_verdict} />
          </TabsContent>
          <TabsContent value="catalyst" className="mt-4">
            <CatalystTab catalyst={proposal?.catalyst_stress_test} />
          </TabsContent>
          <TabsContent value="audit" className="mt-4">
            <AuditTab audit={audit} />
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}
