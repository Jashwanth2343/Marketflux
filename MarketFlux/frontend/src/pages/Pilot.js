import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Plane,
  Loader2,
  Zap,
  Lock,
  Plus,
  Activity as ActivityIcon,
  Inbox,
} from 'lucide-react';

import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Card, CardContent } from '@/components/ui/card';
import { PilotOnboarding } from '@/components/pilot/PilotOnboarding';
import { PersonalityCard } from '@/components/pilot/PersonalityCard';
import { ProposalCard } from '@/components/pilot/ProposalCard';
import { GlassBoxTrade } from '@/components/pilot/GlassBoxTrade';
import { AdversarialDebate } from '@/components/pilot/AdversarialDebate';

const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const ACTIVITY_POLL_MS = 4000;
const PROPOSAL_POLL_MS = 8000;

const ACTIVITY_COLORS = {
  cycle_start: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-400',
  candidates_selected: 'border-blue-500/30 bg-blue-500/10 text-blue-400',
  swarm_running: 'border-violet-500/30 bg-violet-500/10 text-violet-400',
  passed: 'border-green-500/30 bg-green-500/10 text-green-500',
  policy_blocked: 'border-red-500/30 bg-red-500/10 text-red-500',
  no_candidates: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
  cycle_end: 'border-muted-foreground/30 bg-muted text-muted-foreground',
  kill_switch: 'border-red-500/30 bg-red-500/10 text-red-500',
  default: 'border-border bg-muted/40 text-muted-foreground',
};

function activityClasses(type) {
  return ACTIVITY_COLORS[type] || ACTIVITY_COLORS.default;
}

function formatTimestamp(value) {
  if (!value) return '--';
  try {
    return new Date(value).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return String(value);
  }
}

function safeErrorMessage(err) {
  const detail =
    err?.response?.data?.detail ||
    err?.response?.data?.message ||
    err?.message ||
    'Unknown error';
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || d.message || JSON.stringify(d)).join('; ');
  }
  return String(detail);
}

function DisclaimerStrip({ text }) {
  return (
    <div className="border-t border-border bg-muted/30 px-4 py-2 text-[11px] text-muted-foreground leading-relaxed">
      {text ||
        'Marketflux Pilot operates on paper-trading accounts only. Output is research, not financial advice. You retain full responsibility for any approved action.'}
    </div>
  );
}

export default function Pilot() {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [status, setStatus] = useState(null);
  const [consent, setConsent] = useState(null);
  const [consentChecked, setConsentChecked] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);

  const [personalities, setPersonalities] = useState([]);
  const [loadingPersonalities, setLoadingPersonalities] = useState(true);
  const [selectedPersonalityId, setSelectedPersonalityId] = useState(null);

  const [activity, setActivity] = useState([]);
  const [proposals, setProposals] = useState([]);
  const [runningAll, setRunningAll] = useState(false);

  const [glassBoxOpen, setGlassBoxOpen] = useState(false);
  const [glassBoxProposal, setGlassBoxProposal] = useState(null);

  const [showNewDialog, setShowNewDialog] = useState(false);
  // Map of proposalId -> true (dismissed/hidden locally)
  const dismissedRef = useRef(new Set());

  // Auth gate
  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/auth');
    }
  }, [authLoading, user, navigate]);

  // Initial fetch: status + consent
  useEffect(() => {
    if (authLoading || !user) return undefined;
    let active = true;
    const run = async () => {
      try {
        const [statusRes, consentRes] = await Promise.all([
          axios.get(`${API}/api/pilot/status`, { withCredentials: true }),
          axios.get(`${API}/api/pilot/consent`, { withCredentials: true }),
        ]);
        if (!active) return;
        setStatus(statusRes?.data || null);
        const item = consentRes?.data?.item || null;
        setConsent(item);
        if (!item || !item.accept_paper_only) {
          setShowOnboarding(true);
        }
      } catch (err) {
        if (!active) return;
        if (err?.response?.status === 401) {
          navigate('/auth');
          return;
        }
        toast.error(`Could not load Pilot status. Backend says: ${safeErrorMessage(err)}`);
      } finally {
        if (active) setConsentChecked(true);
      }
    };
    run();
    return () => {
      active = false;
    };
  }, [authLoading, user, navigate]);

  // Load personalities once consent is in place
  const loadPersonalities = useCallback(async () => {
    setLoadingPersonalities(true);
    try {
      const res = await axios.get(`${API}/api/pilot/personalities`, { withCredentials: true });
      setPersonalities(Array.isArray(res?.data?.items) ? res.data.items : []);
    } catch (err) {
      if (err?.response?.status === 401) {
        navigate('/auth');
        return;
      }
      toast.error(`Could not load personalities. Backend says: ${safeErrorMessage(err)}`);
    } finally {
      setLoadingPersonalities(false);
    }
  }, [navigate]);

  useEffect(() => {
    if (!consentChecked || !consent || !consent.accept_paper_only) return;
    loadPersonalities();
  }, [consentChecked, consent, loadPersonalities]);

  // Activity polling
  useEffect(() => {
    if (!consentChecked || !consent || !consent.accept_paper_only) return undefined;

    let cancelled = false;
    const fetchActivity = async () => {
      try {
        const params = new URLSearchParams();
        if (selectedPersonalityId) params.set('personality_id', selectedPersonalityId);
        params.set('limit', '50');
        const url = `${API}/api/pilot/activity?${params.toString()}`;
        const res = await axios.get(url, { withCredentials: true });
        if (cancelled) return;
        setActivity(Array.isArray(res?.data?.items) ? res.data.items : []);
      } catch (err) {
        if (cancelled) return;
        if (err?.response?.status === 401) {
          navigate('/auth');
        }
        // Silent on transient polling errors.
      }
    };
    fetchActivity();
    const id = setInterval(fetchActivity, ACTIVITY_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [consentChecked, consent, selectedPersonalityId, navigate]);

  // Proposal polling
  useEffect(() => {
    if (!consentChecked || !consent || !consent.accept_paper_only) return undefined;

    let cancelled = false;
    const fetchProposals = async () => {
      try {
        const params = new URLSearchParams();
        params.set('status', 'pending');
        const url = `${API}/api/pilot/proposals?${params.toString()}`;
        const res = await axios.get(url, { withCredentials: true });
        if (cancelled) return;
        const items = Array.isArray(res?.data?.items) ? res.data.items : [];
        setProposals(items.filter((p) => !dismissedRef.current.has(p.id)));
      } catch (err) {
        if (cancelled) return;
        if (err?.response?.status === 401) {
          navigate('/auth');
        }
      }
    };
    fetchProposals();
    const id = setInterval(fetchProposals, PROPOSAL_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [consentChecked, consent, navigate]);

  const filteredActivity = useMemo(() => {
    if (!selectedPersonalityId) return activity;
    return activity.filter((evt) => evt.personality_id === selectedPersonalityId);
  }, [activity, selectedPersonalityId]);

  const visibleProposals = useMemo(() => {
    return proposals.filter((p) => !dismissedRef.current.has(p.id));
  }, [proposals]);

  const selectedProposalDebate = useMemo(() => {
    if (!selectedPersonalityId) return null;
    const matching = proposals
      .filter((p) => p.personality_id === selectedPersonalityId)
      .sort((a, b) => {
        const ta = new Date(a.created_at || 0).getTime();
        const tb = new Date(b.created_at || 0).getTime();
        return tb - ta;
      });
    return matching[0] || null;
  }, [proposals, selectedPersonalityId]);

  const handleConsented = (item) => {
    setConsent(item || null);
    setShowOnboarding(false);
    // Trigger personalities load
    loadPersonalities();
  };

  const handlePersonalityUpdated = (item, meta) => {
    if (!item) return;
    setPersonalities((prev) => {
      const idx = prev.findIndex((p) => p.id === item.id);
      if (idx === -1) return [...prev, item];
      const copy = [...prev];
      copy[idx] = { ...copy[idx], ...item };
      return copy;
    });
    if (meta?.isClone) {
      // Refresh full list to ensure ordering / new item is present
      loadPersonalities();
    }
  };

  const handleProposalChanged = (item) => {
    if (!item) return;
    setProposals((prev) => {
      const idx = prev.findIndex((p) => p.id === item.id);
      if (idx === -1) {
        // If status is still pending and matches filters, add
        if (item.status === 'pending' && !dismissedRef.current.has(item.id)) {
          return [item, ...prev];
        }
        return prev;
      }
      const copy = [...prev];
      copy[idx] = { ...copy[idx], ...item };
      return copy;
    });
  };

  const handleDismissProposal = (id) => {
    dismissedRef.current.add(id);
    setProposals((prev) => prev.filter((p) => p.id !== id));
  };

  const runAll = async () => {
    const activeOnes = personalities.filter((p) => !p.paused);
    if (activeOnes.length === 0) {
      toast.info('No active personalities to run. Resume one first.');
      return;
    }
    setRunningAll(true);
    let totalFound = 0;
    let failures = 0;
    try {
      const results = await Promise.allSettled(
        activeOnes.map((p) =>
          axios.post(
            `${API}/api/pilot/personalities/${p.id}/propose`,
            { max_candidates: 5, dry_run: false },
            { withCredentials: true }
          )
        )
      );
      results.forEach((r, idx) => {
        const name = activeOnes[idx]?.name || 'Personality';
        if (r.status === 'fulfilled') {
          const data = r.value?.data || {};
          if (data.ok === false) {
            toast.info(`${name}: ${data.reason || data.message || 'No proposals.'}`);
          } else {
            const count = Array.isArray(data.proposals) ? data.proposals.length : 0;
            totalFound += count;
            toast.success(`${name} found ${count} proposal${count === 1 ? '' : 's'}.`);
          }
        } else {
          failures += 1;
          toast.error(`${name} failed. Backend says: ${safeErrorMessage(r.reason)}`);
        }
      });
      if (failures === 0) {
        toast.success(`Run All complete. ${totalFound} new proposals.`);
      }
    } finally {
      setRunningAll(false);
    }
  };

  const openDetails = (proposal) => {
    setGlassBoxProposal(proposal);
    setGlassBoxOpen(true);
  };

  // ---------------- Render guards ----------------
  if (authLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }
  if (!user) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <Card className="max-w-md w-full">
          <CardContent className="p-8 text-center space-y-3">
            <Lock className="mx-auto w-8 h-8 text-primary" />
            <h2 className="text-xl font-semibold">Login required</h2>
            <p className="text-sm text-muted-foreground">
              Pilot is private to your account. Sign in to continue.
            </p>
            <Button onClick={() => navigate('/auth')}>Continue to login</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ---------------- Layout ----------------
  return (
    <div className="flex flex-col flex-1 min-h-full" data-testid="pilot-page">
      {/* Header */}
      <div className="border-b border-border bg-card/40 px-4 md:px-6 py-3 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <Plane className="w-5 h-5 text-primary" />
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-foreground truncate">
              Pilot — AI Portfolio Manager
            </h1>
            <p className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
              Adversarial swarm · paper execution · user-approved
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="bg-yellow-500/10 text-yellow-500 border border-yellow-500/30 px-2 py-1 rounded text-xs font-mono uppercase tracking-wider">
            Paper only · Not advice
          </span>
          <Button
            size="sm"
            onClick={runAll}
            disabled={runningAll || loadingPersonalities}
            className="gap-2 font-mono text-xs uppercase tracking-wider"
          >
            {runningAll ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4" />
            )}
            Run all
          </Button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[28%_44%_28%] gap-4 p-4 md:p-6 overflow-auto">
        {/* Left column: personalities */}
        <section className="space-y-3 min-w-0">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
              Personalities
            </h2>
            <span className="text-[10px] font-mono text-muted-foreground">
              {personalities.length}
            </span>
          </div>

          {loadingPersonalities ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-primary" />
            </div>
          ) : personalities.length === 0 ? (
            <div className="bg-card border border-dashed border-border rounded-lg p-6 text-center text-sm text-muted-foreground">
              No personalities yet. Clone Atlas, Sage, or Vega to get started.
            </div>
          ) : (
            <div className="space-y-3">
              {personalities.map((p) => (
                <PersonalityCard
                  key={p.id}
                  personality={p}
                  selected={selectedPersonalityId === p.id}
                  onSelect={(item) =>
                    setSelectedPersonalityId((prev) => (prev === item.id ? null : item.id))
                  }
                  onUpdated={handlePersonalityUpdated}
                  onProposed={() => {
                    // Trigger a fresh proposals fetch by clearing dismissed for any new items
                    // The polling loop will pick up new pending proposals on next tick.
                  }}
                />
              ))}
            </div>
          )}

          <Button
            variant="outline"
            className="w-full gap-2 font-mono text-xs uppercase tracking-wider"
            onClick={() => setShowNewDialog(true)}
          >
            <Plus className="w-3 h-3" /> New Personality
          </Button>
        </section>

        {/* Middle column: activity feed */}
        <section className="space-y-3 min-w-0">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <ActivityIcon className="w-3 h-3" /> Live activity
            </h2>
            {selectedPersonalityId ? (
              <button
                type="button"
                className="text-[10px] font-mono uppercase tracking-wider text-primary hover:underline"
                onClick={() => setSelectedPersonalityId(null)}
              >
                Clear filter
              </button>
            ) : null}
          </div>

          {selectedPersonalityId && selectedProposalDebate ? (
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-3">
                Latest debate · {selectedProposalDebate.ticker}
              </div>
              <AdversarialDebate
                transcript={selectedProposalDebate.debate_transcript || []}
                verdict={selectedProposalDebate.dissent_summary || null}
                compact
              />
            </div>
          ) : null}

          <div className="space-y-2">
            {filteredActivity.length === 0 ? (
              <div className="bg-card border border-dashed border-border rounded-lg p-6 text-center text-sm text-muted-foreground">
                Activity feed is quiet. Press Propose or Run All to start a cycle.
              </div>
            ) : (
              filteredActivity.map((evt) => (
                <div
                  key={evt.id || `${evt.timestamp}-${evt.event_type}`}
                  className={`rounded-md border px-3 py-2 text-xs flex items-start justify-between gap-3 ${activityClasses(
                    evt.event_type
                  )}`}
                >
                  <div className="min-w-0">
                    <div className="font-mono uppercase tracking-wider text-[10px] mb-0.5">
                      {evt.event_type || 'event'}
                    </div>
                    <div className="text-foreground/90 break-words">
                      {evt.message ||
                        (evt.payload && typeof evt.payload === 'object'
                          ? Object.entries(evt.payload)
                              .slice(0, 3)
                              .map(([k, v]) => `${k}=${typeof v === 'object' ? '…' : v}`)
                              .join(' · ')
                          : '')}
                    </div>
                  </div>
                  <div className="text-[10px] font-mono shrink-0 text-muted-foreground/80">
                    {formatTimestamp(evt.timestamp)}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        {/* Right column: proposals */}
        <section className="space-y-3 min-w-0">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <Inbox className="w-3 h-3" /> Pending proposals
            </h2>
            <span className="text-[10px] font-mono text-muted-foreground">
              {visibleProposals.length}
            </span>
          </div>
          {visibleProposals.length === 0 ? (
            <div className="bg-card border border-dashed border-border rounded-lg p-6 text-center text-sm text-muted-foreground">
              No pending proposals. Run a personality to generate new ones.
            </div>
          ) : (
            <div className="space-y-3">
              {visibleProposals.map((p) => (
                <ProposalCard
                  key={p.id}
                  proposal={p}
                  onDetails={openDetails}
                  onChanged={handleProposalChanged}
                  onDismiss={handleDismissProposal}
                />
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Footer disclaimer */}
      <DisclaimerStrip text={status?.disclaimer} />

      {/* Onboarding */}
      <PilotOnboarding
        open={showOnboarding}
        onOpenChange={setShowOnboarding}
        onConsented={handleConsented}
      />

      {/* GlassBox Sheet */}
      <GlassBoxTrade
        open={glassBoxOpen}
        onOpenChange={(o) => {
          setGlassBoxOpen(o);
          if (!o) setGlassBoxProposal(null);
        }}
        proposalId={glassBoxProposal?.id || null}
        initialProposal={glassBoxProposal}
      />

      {/* "New personality" stub dialog */}
      <Dialog open={showNewDialog} onOpenChange={setShowNewDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New personality</DialogTitle>
            <DialogDescription>
              Custom personality designer ships in Week 4 — clone Atlas (or any seed) and edit for
              now. Cloning is available from each seed card.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setShowNewDialog(false)}>Got it</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
