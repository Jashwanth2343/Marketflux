import { lazy, Suspense, useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Plane, Wand2, ListChecks, Wallet, Brain, Activity,
  TrendingUp, TrendingDown, DollarSign, BarChart3,
  Loader2, RefreshCw, Inbox, ShieldCheck, AlertTriangle,
  Zap, Target, Shield, Clock, ChevronRight,
} from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import api from '@/lib/api';
import alpacaApi from '@/lib/alpacaApi';
import { useAuth } from '@/contexts/AuthContext';
import { ProposalCard } from '@/components/pilot/ProposalCard';
import { GlassBoxTrade } from '@/components/pilot/GlassBoxTrade';

const StrategyTerminal = lazy(() => import('@/components/StrategyTerminal'));

function fmt(v) {
  if (v == null || !Number.isFinite(Number(v))) return '$0.00';
  return Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

function pct(v) {
  if (v == null || !Number.isFinite(Number(v))) return '0.00%';
  return `${(Number(v) * 100).toFixed(2)}%`;
}

function StatCard({ label, value, sub, icon: Icon, color = 'text-primary' }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 hover:border-white/10 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">{label}</span>
        {Icon && <Icon className={`w-4 h-4 ${color} opacity-60`} />}
      </div>
      <p className="text-xl font-bold font-mono text-foreground">{value}</p>
      {sub && <p className={`text-xs font-mono mt-0.5 ${sub.startsWith('-') ? 'text-red-400' : 'text-emerald-400'}`}>{sub}</p>}
    </div>
  );
}

function ActivityItem({ event }) {
  const colors = {
    cycle_start: 'text-blue-400', cycle_end: 'text-emerald-400',
    swarm_running: 'text-cyan-400', candidates_selected: 'text-amber-400',
    passed: 'text-muted-foreground', policy_blocked: 'text-red-400',
    kill_switch: 'text-red-500', skipped: 'text-muted-foreground',
  };
  const icons = {
    cycle_start: Zap, cycle_end: Target, swarm_running: Brain,
    candidates_selected: BarChart3, kill_switch: Shield,
  };
  const Icon = icons[event.event_type] || Activity;
  const color = colors[event.event_type] || 'text-muted-foreground';
  const time = event.created_at ? new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

  return (
    <div className="flex items-start gap-3 py-2 border-b border-white/[0.04] last:border-0">
      <Icon className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${color}`} />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-mono text-foreground/80 truncate">{event.message}</p>
      </div>
      <span className="text-[10px] font-mono text-muted-foreground flex-shrink-0">{time}</span>
    </div>
  );
}

function PositionRow({ pos }) {
  const pl = Number(pos.unrealized_pl || 0);
  const plPct = Number(pos.unrealized_plpc || 0);
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-white/[0.04] last:border-0">
      <div className="flex items-center gap-3">
        <span className="text-sm font-mono font-bold text-primary">{pos.symbol}</span>
        <span className="text-xs font-mono text-muted-foreground">{pos.qty} shares</span>
      </div>
      <div className="text-right">
        <span className={`text-xs font-mono font-semibold ${pl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          {pl >= 0 ? '+' : ''}{fmt(pl)}
        </span>
        <span className={`text-[10px] font-mono ml-1.5 ${pl >= 0 ? 'text-emerald-400/60' : 'text-red-400/60'}`}>
          {pl >= 0 ? '+' : ''}{pct(plPct)}
        </span>
      </div>
    </div>
  );
}

function PersonalityPill({ personality, onPropose, generating }) {
  const isActive = !personality.paused;
  return (
    <div className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5 hover:border-white/10 transition-colors">
      <div className="flex items-center gap-2.5">
        <div className={`w-2 h-2 rounded-full ${isActive ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.4)]' : 'bg-muted-foreground/30'}`} />
        <div>
          <span className="text-sm font-mono font-semibold text-foreground">{personality.name}</span>
          {personality.is_seed && <span className="text-[9px] font-mono text-amber-400/70 ml-1.5 uppercase">seed</span>}
        </div>
      </div>
      <Button
        size="sm"
        variant="ghost"
        disabled={generating || personality.paused}
        onClick={() => onPropose(personality.id)}
        className="text-[10px] font-mono h-7 px-2.5 gap-1 text-primary hover:text-primary hover:bg-primary/10"
      >
        {generating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
        Propose
      </Button>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>
  );
}

const tabs = [
  { value: 'copilot', label: 'Command Center', icon: Plane },
  { value: 'studio', label: 'Strategy Studio', icon: Wand2 },
];

export default function Copilot() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'copilot';
  const { user } = useAuth();

  const [consentStatus, setConsentStatus] = useState(null);
  const [proposals, setProposals] = useState([]);
  const [personalities, setPersonalities] = useState([]);
  const [account, setAccount] = useState(null);
  const [positions, setPositions] = useState([]);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [detailId, setDetailId] = useState(null);
  const [detailProposal, setDetailProposal] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const fetchAll = useCallback(async () => {
    if (!user) { setLoading(false); return; }
    setLoading(true);
    const settled = await Promise.allSettled([
      api.get('/pilot/consent'),
      api.get('/pilot/proposals', { params: { status: 'pending', limit: 20 } }),
      api.get('/pilot/personalities'),
      alpacaApi.getAccount(),
      alpacaApi.getPositions(),
      api.get('/pilot/activity', { params: { limit: 15 } }),
    ]);
    setConsentStatus(settled[0].status === 'fulfilled' ? settled[0].value?.data : null);
    setProposals(settled[1].status === 'fulfilled' ? (settled[1].value?.data?.items || []) : []);
    setPersonalities(settled[2].status === 'fulfilled' ? (settled[2].value?.data?.items || []) : []);
    const acctData = settled[3].status === 'fulfilled' ? settled[3].value : null;
    setAccount(acctData?.item || acctData);
    const posData = settled[4].status === 'fulfilled' ? settled[4].value : null;
    setPositions(Array.isArray(posData?.items || posData) ? (posData?.items || posData) : []);
    setActivity(settled[5].status === 'fulfilled' ? (settled[5].value?.data?.items || []) : []);
    setLoading(false);
  }, [user]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleTabChange = (value) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', value);
      return next;
    }, { replace: true });
  };

  const grantConsent = async () => {
    try {
      await api.post('/pilot/consent', {
        accept_paper_only: true, accept_not_advice: true, accept_audit_logging: true,
      });
      toast.success('Copilot consent granted');
      fetchAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to grant consent');
    }
  };

  const generateProposal = async (personalityId) => {
    setGenerating(true);
    try {
      await api.post(`/pilot/personalities/${personalityId}/propose`, {});
      toast.success('Proposal generation started — scanning markets...');
      setTimeout(fetchAll, 3000);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to generate proposal');
    } finally {
      setGenerating(false);
    }
  };

  const handleDetails = (proposal) => {
    setDetailId(proposal.id);
    setDetailProposal(proposal);
    setDetailOpen(true);
  };

  const handleChanged = (updated) => {
    setProposals((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
  };

  const handleDismiss = (id) => {
    setProposals((prev) => prev.filter((p) => p.id !== id));
  };

  if (!user) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-10 text-center max-w-md">
          <Plane className="w-14 h-14 text-primary mx-auto mb-5" style={{ filter: 'drop-shadow(0 0 12px rgba(0,255,65,0.3))' }} />
          <h2 className="text-xl font-bold font-mono text-foreground mb-2">AI Trading Copilot</h2>
          <p className="text-sm text-muted-foreground mb-6 font-mono">
            Sign in to access your AI-powered trading command center.
          </p>
          <Button onClick={() => window.location.href = '/auth'} className="font-mono text-sm gap-2 bg-primary text-black hover:bg-primary/90">
            Sign In to Continue
          </Button>
        </div>
      </div>
    );
  }

  if (consentStatus && !consentStatus.item) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="rounded-2xl border border-primary/20 bg-white/[0.02] p-10 text-center max-w-lg" style={{ boxShadow: '0 0 60px rgba(0,255,65,0.05)' }}>
          <ShieldCheck className="w-14 h-14 text-primary mx-auto mb-5" style={{ filter: 'drop-shadow(0 0 12px rgba(0,255,65,0.3))' }} />
          <h2 className="text-xl font-bold font-mono text-foreground mb-3">Enable Trading Copilot</h2>
          <p className="text-sm text-muted-foreground mb-2 font-mono">
            AI agents will analyze markets, run adversarial debates, and generate trade proposals for your review.
          </p>
          <p className="text-xs text-muted-foreground mb-8 font-mono opacity-60">
            Paper trading only. You approve every trade. Full audit trail.
          </p>
          <div className="flex flex-col gap-3 text-left mb-8 max-w-xs mx-auto">
            {[
              { icon: Shield, text: 'Paper trading only — no real money' },
              { icon: Target, text: 'You approve every trade before execution' },
              { icon: Activity, text: 'Full audit trail of all AI decisions' },
            ].map(({ icon: I, text }) => (
              <div key={text} className="flex items-center gap-3 text-xs font-mono text-foreground/70">
                <I className="w-4 h-4 text-primary flex-shrink-0" />
                {text}
              </div>
            ))}
          </div>
          <Button onClick={grantConsent} className="font-mono text-sm gap-2 bg-primary text-black hover:bg-primary/90 px-8">
            <ShieldCheck className="w-4 h-4" /> Grant Consent & Enter
          </Button>
        </div>
      </div>
    );
  }

  const equity = Number(account?.equity || 0);
  const cash = Number(account?.cash || 0);
  const pl = Number(account?.unrealized_pl || account?.profit_loss || 0);
  const dayPl = Number(account?.equity) - Number(account?.last_equity || account?.equity);
  const activePersonalities = personalities.filter((p) => !p.paused && (p.status === 'active' || !p.status));

  return (
    <div className="min-h-screen bg-background">
      <div className="px-4 md:px-6 pt-4 pb-2">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Plane className="w-6 h-6 text-primary" style={{ filter: 'drop-shadow(0 0 8px rgba(0,255,65,0.4))' }} />
              <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-emerald-400 rounded-full shadow-[0_0_4px_rgba(52,211,153,0.6)]" />
            </div>
            <div>
              <h1 className="text-lg font-bold font-mono tracking-tight text-foreground">Trading Copilot</h1>
              <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-widest">Command Center</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Tabs value={activeTab} onValueChange={handleTabChange}>
              <TabsList className="bg-white/5 border border-white/10 p-0.5 h-8">
                {tabs.map(({ value, label, icon: Icon }) => (
                  <TabsTrigger
                    key={value}
                    value={value}
                    className="data-[state=active]:bg-primary/20 data-[state=active]:text-primary font-mono text-[10px] uppercase tracking-wider gap-1.5 h-7 px-3"
                  >
                    <Icon className="w-3 h-3" />
                    {label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <Button size="sm" variant="ghost" onClick={fetchAll} disabled={loading} className="text-xs font-mono h-8 w-8 p-0">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </div>

      {activeTab === 'copilot' && (
        <div className="px-4 md:px-6 pb-6">
          {/* Stats Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            <StatCard label="Portfolio Equity" value={fmt(equity)} icon={DollarSign} />
            <StatCard label="Cash Available" value={fmt(cash)} icon={Wallet} />
            <StatCard label="Unrealized P&L" value={fmt(pl)} sub={pl !== 0 ? `${pl > 0 ? '+' : ''}${fmt(pl)}` : undefined} icon={pl >= 0 ? TrendingUp : TrendingDown} color={pl >= 0 ? 'text-emerald-400' : 'text-red-400'} />
            <StatCard label="Day P&L" value={fmt(dayPl)} sub={dayPl !== 0 ? `${dayPl > 0 ? '+' : ''}${fmt(dayPl)}` : undefined} icon={dayPl >= 0 ? TrendingUp : TrendingDown} color={dayPl >= 0 ? 'text-emerald-400' : 'text-red-400'} />
          </div>

          {/* Main Grid: Proposals + Sidebar */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            {/* Left: Proposals */}
            <div className="lg:col-span-7 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-mono font-semibold text-foreground uppercase tracking-widest flex items-center gap-2">
                  <Target className="w-3.5 h-3.5 text-primary" />
                  Pending Proposals
                  {proposals.length > 0 && (
                    <span className="bg-primary/20 text-primary text-[10px] px-1.5 py-0.5 rounded-full font-bold">
                      {proposals.length}
                    </span>
                  )}
                </h3>
              </div>

              {loading && !proposals.length ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                </div>
              ) : proposals.length === 0 ? (
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-8 text-center">
                  <Inbox className="w-8 h-8 text-muted-foreground mx-auto mb-3 opacity-30" />
                  <p className="text-sm text-muted-foreground font-mono mb-1">No pending proposals</p>
                  <p className="text-[10px] text-muted-foreground/60 font-mono mb-4">
                    {activePersonalities.length > 0
                      ? 'Click "Propose" on a personality to scan markets'
                      : 'Create a personality in the Strategy Studio to get started'}
                  </p>
                  {activePersonalities.length === 0 && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleTabChange('studio')}
                      className="text-xs font-mono gap-1"
                    >
                      <Wand2 className="w-3 h-3" /> Open Strategy Studio
                    </Button>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {proposals.map((p) => (
                    <ProposalCard
                      key={p.id}
                      proposal={p}
                      onDetails={handleDetails}
                      onChanged={handleChanged}
                      onDismiss={handleDismiss}
                    />
                  ))}
                </div>
              )}

              {proposals.some((p) => !p.policy_verdict?.allowed) && (
                <div className="flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs font-mono text-amber-400">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                  Some proposals are blocked by policy. Review details before approving.
                </div>
              )}
            </div>

            {/* Right: Sidebar */}
            <div className="lg:col-span-5 space-y-4">
              {/* AI Personalities */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-xs font-mono font-semibold text-foreground uppercase tracking-widest flex items-center gap-2">
                    <Brain className="w-3.5 h-3.5 text-cyan-400" />
                    AI Personalities
                  </h4>
                  <span className="text-[10px] font-mono text-muted-foreground">
                    {activePersonalities.length} active
                  </span>
                </div>
                {personalities.length === 0 ? (
                  <p className="text-xs font-mono text-muted-foreground/60 text-center py-4">
                    No personalities configured yet
                  </p>
                ) : (
                  <div className="space-y-2">
                    {personalities.map((p) => (
                      <PersonalityPill
                        key={p.id}
                        personality={p}
                        onPropose={generateProposal}
                        generating={generating}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Positions */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-xs font-mono font-semibold text-foreground uppercase tracking-widest flex items-center gap-2">
                    <BarChart3 className="w-3.5 h-3.5 text-amber-400" />
                    Open Positions
                  </h4>
                  <span className="text-[10px] font-mono text-muted-foreground">{positions.length}</span>
                </div>
                {positions.length === 0 ? (
                  <p className="text-xs font-mono text-muted-foreground/60 text-center py-4">No open positions</p>
                ) : (
                  <div>{positions.map((p) => <PositionRow key={p.symbol} pos={p} />)}</div>
                )}
              </div>

              {/* Activity Feed */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-xs font-mono font-semibold text-foreground uppercase tracking-widest flex items-center gap-2">
                    <Activity className="w-3.5 h-3.5 text-emerald-400" />
                    Agent Activity
                  </h4>
                  <Clock className="w-3 h-3 text-muted-foreground" />
                </div>
                {activity.length === 0 ? (
                  <p className="text-xs font-mono text-muted-foreground/60 text-center py-4">No recent activity</p>
                ) : (
                  <div className="max-h-48 overflow-y-auto">
                    {activity.slice(0, 10).map((e, i) => <ActivityItem key={e.id || i} event={e} />)}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'studio' && (
        <div className="px-4 md:px-6 pb-6">
          <Suspense fallback={<LoadingSpinner />}>
            <StrategyTerminal embedded />
          </Suspense>
        </div>
      )}

      <GlassBoxTrade
        open={detailOpen}
        onOpenChange={setDetailOpen}
        proposalId={detailId}
        initialProposal={detailProposal}
      />
    </div>
  );
}
