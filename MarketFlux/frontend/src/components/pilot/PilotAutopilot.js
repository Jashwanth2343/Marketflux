import { useEffect, useState, useCallback } from 'react';
import { Loader2, Users, ListChecks, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { PersonalityCard } from '@/components/pilot/PersonalityCard';
import { ProposalCard } from '@/components/pilot/ProposalCard';
import { GlassBoxTrade } from '@/components/pilot/GlassBoxTrade';

function SectionHeader({ icon: Icon, title, sub }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <Icon className="h-4 w-4 text-primary" />
      <div>
        <div className="text-sm font-semibold text-foreground">{title}</div>
        {sub && <div className="text-[11px] text-muted-foreground">{sub}</div>}
      </div>
    </div>
  );
}

function ConsentGate({ onGranted }) {
  const [busy, setBusy] = useState(false);
  const grant = async () => {
    setBusy(true);
    try {
      await api.post('/pilot/consent', {
        accept_paper_only: true,
        accept_not_advice: true,
        accept_audit_logging: true,
      });
      toast.success('Paper-trading consent recorded.');
      onGranted?.();
    } catch (err) {
      toast.error('Could not record consent', {
        description: err?.response?.data?.detail || err?.message,
      });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="rounded-2xl border border-amber-500/30 bg-amber-500/[0.06] p-5">
      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <ShieldCheck className="h-4 w-4 text-amber-400" />
        Enable autonomous pilots
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
        Pilots propose trades on your <span className="font-semibold text-foreground">paper account only</span>.
        This is not financial advice, and every action is audit-logged. You can kill any
        pilot instantly at any time.
      </p>
      <Button onClick={grant} disabled={busy} className="mt-4 h-9 gap-2 rounded-lg text-xs font-semibold">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />}
        I understand — enable paper pilots
      </Button>
    </div>
  );
}

export default function PilotAutopilot() {
  const [consent, setConsent] = useState(null); // null = unknown, object/false
  const [personalities, setPersonalities] = useState([]);
  const [proposals, setProposals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [detailId, setDetailId] = useState(null);
  const [detailInitial, setDetailInitial] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: c } = await api.get('/pilot/consent');
      const granted = !!(c?.item && c.item.accept_paper_only);
      setConsent(granted);
      if (granted) {
        const [{ data: p }, { data: pr }] = await Promise.all([
          api.get('/pilot/personalities'),
          api.get('/pilot/proposals', { params: { status: 'pending', limit: 50 } }),
        ]);
        setPersonalities(p?.items || []);
        setProposals(pr?.items || []);
      }
    } catch (err) {
      // 401 = not logged in; surface empty state, don't toast-spam
      if (err?.response?.status !== 401) {
        toast.error('Could not load pilots', { description: err?.message });
      }
      setConsent(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const refreshProposals = useCallback(async () => {
    try {
      const { data } = await api.get('/pilot/proposals', { params: { status: 'pending', limit: 50 } });
      setProposals(data?.items || []);
    } catch {
      /* keep stale list */
    }
  }, []);

  const openDetails = useCallback((proposal) => {
    setDetailInitial(proposal || null);
    setDetailId(proposal?.id || null);
  }, []);

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!consent) {
    return <ConsentGate onGranted={load} />;
  }

  return (
    <div className="space-y-8">
      <section>
        <SectionHeader
          icon={Users}
          title="Pilot personalities"
          sub="Autonomous paper traders — pause, clone, inspect the journal, or kill instantly."
        />
        {personalities.length === 0 ? (
          <div className="rounded-xl border border-border bg-card/50 p-5 text-xs text-muted-foreground">
            No pilots yet. They are seeded automatically on first load — refresh in a moment.
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {personalities.map((p) => (
              <PersonalityCard
                key={p.id}
                personality={p}
                selected={selectedId === p.id}
                onSelect={(pl) => setSelectedId((cur) => (cur === pl.id ? null : pl.id))}
                onUpdated={(updated) =>
                  setPersonalities((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))
                }
                onProposed={refreshProposals}
              />
            ))}
          </div>
        )}
      </section>

      <section>
        <SectionHeader
          icon={ListChecks}
          title={`Pending proposals${proposals.length ? ` (${proposals.length})` : ''}`}
          sub="Approve to route to your paper account, or inspect the full audit trail first."
        />
        {proposals.length === 0 ? (
          <div className="rounded-xl border border-border bg-card/50 p-5 text-xs text-muted-foreground">
            No pending proposals. Pilots will surface trade ideas here for your approval.
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {proposals.map((pr) => (
              <ProposalCard
                key={pr.id}
                proposal={pr}
                onDetails={openDetails}
                onChanged={(item) => {
                  if (item?.status && item.status !== 'pending') {
                    setProposals((prev) => prev.filter((x) => x.id !== item.id));
                  } else {
                    setProposals((prev) => prev.map((x) => (x.id === item.id ? item : x)));
                  }
                }}
                onDismiss={(id) => setProposals((prev) => prev.filter((x) => x.id !== id))}
              />
            ))}
          </div>
        )}
      </section>

      <GlassBoxTrade
        open={!!detailId}
        onOpenChange={(open) => {
          if (!open) {
            setDetailId(null);
            setDetailInitial(null);
          }
        }}
        proposalId={detailId}
        initialProposal={detailInitial}
      />
    </div>
  );
}
