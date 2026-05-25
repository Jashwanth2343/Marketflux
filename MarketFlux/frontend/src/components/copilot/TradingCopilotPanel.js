import { useEffect, useState, useCallback } from 'react';
import { Plane, Loader2, RefreshCw, Inbox, ShieldCheck, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { ProposalCard } from '@/components/pilot/ProposalCard';
import { GlassBoxTrade } from '@/components/pilot/GlassBoxTrade';
import AccountSummary from '@/components/copilot/AccountSummary';
import api from '@/lib/api';

export default function TradingCopilotPanel() {
    const [consentStatus, setConsentStatus] = useState(null);
    const [proposals, setProposals] = useState([]);
    const [personalities, setPersonalities] = useState([]);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [detailId, setDetailId] = useState(null);
    const [detailProposal, setDetailProposal] = useState(null);
    const [detailOpen, setDetailOpen] = useState(false);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        const settled = await Promise.allSettled([
            api.get('/pilot/consent'),
            api.get('/pilot/proposals', { params: { status: 'pending', limit: 20 } }),
            api.get('/pilot/personalities'),
        ]);
        if (settled.every((s) => s.status === 'rejected')) {
            toast.error('Failed to load copilot data');
        }
        const consentRes = settled[0].status === 'fulfilled' ? settled[0].value : null;
        const proposalRes = settled[1].status === 'fulfilled' ? settled[1].value : null;
        const personalityRes = settled[2].status === 'fulfilled' ? settled[2].value : null;
        setConsentStatus(consentRes?.data || null);
        setProposals(Array.isArray(proposalRes?.data?.items) ? proposalRes.data.items : []);
        setPersonalities(Array.isArray(personalityRes?.data?.items) ? personalityRes.data.items : []);
        setLoading(false);
    }, []);

    useEffect(() => {
        fetchAll();
        const interval = setInterval(fetchAll, 30000);
        return () => clearInterval(interval);
    }, [fetchAll]);

    const grantConsent = async () => {
        try {
            await api.post('/pilot/consent', {
                accept_paper_only: true,
                accept_not_advice: true,
                accept_audit_logging: true,
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
            toast.success('Proposal generation started');
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

    if (loading && !proposals.length) {
        return (
            <div className="flex items-center justify-center py-16">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
        );
    }

    if (consentStatus && !consentStatus.item) {
        return (
            <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 text-center max-w-lg mx-auto">
                <ShieldCheck className="w-12 h-12 text-primary mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-foreground mb-2">Enable Trading Copilot</h3>
                <p className="text-sm text-muted-foreground mb-1">
                    The AI copilot analyzes markets, generates trade proposals, and executes
                    approved trades on your Alpaca paper account.
                </p>
                <p className="text-xs text-muted-foreground mb-6">
                    No real money is involved. You must approve each trade before execution.
                </p>
                <Button onClick={grantConsent} className="font-mono text-sm gap-2">
                    <ShieldCheck className="w-4 h-4" /> Grant Consent
                </Button>
            </div>
        );
    }

    const activePersonalities = personalities.filter((p) => p.status === 'active' || !p.status);

    return (
        <>
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                {/* Main: Proposals */}
                <div className="xl:col-span-2 space-y-4">
                    <div className="flex items-center justify-between">
                        <h3 className="text-sm font-mono font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
                            <Plane className="w-4 h-4 text-primary" />
                            Pending Proposals
                        </h3>
                        <div className="flex items-center gap-2">
                            <Button size="sm" variant="ghost" onClick={fetchAll} disabled={loading} className="text-xs font-mono h-7">
                                <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                            </Button>
                        </div>
                    </div>

                    {proposals.length === 0 && (
                        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-8 text-center">
                            <Inbox className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-50" />
                            <p className="text-sm text-muted-foreground font-mono mb-4">No pending proposals</p>
                            {activePersonalities.length > 0 && (
                                <div className="flex flex-wrap justify-center gap-2">
                                    {activePersonalities.map((p) => (
                                        <Button
                                            key={p.id}
                                            size="sm"
                                            variant="outline"
                                            disabled={generating}
                                            onClick={() => generateProposal(p.id)}
                                            className="text-xs font-mono gap-1"
                                        >
                                            {generating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plane className="w-3 h-3" />}
                                            Generate ({p.name || 'Pilot'})
                                        </Button>
                                    ))}
                                </div>
                            )}
                            {activePersonalities.length === 0 && (
                                <p className="text-xs text-muted-foreground font-mono">
                                    No active pilot personalities configured. Create one in the Pilot settings.
                                </p>
                            )}
                        </div>
                    )}

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

                    {activePersonalities.length > 0 && proposals.length > 0 && (
                        <div className="flex flex-wrap gap-2 pt-2">
                            {activePersonalities.map((p) => (
                                <Button
                                    key={p.id}
                                    size="sm"
                                    variant="outline"
                                    disabled={generating}
                                    onClick={() => generateProposal(p.id)}
                                    className="text-xs font-mono gap-1"
                                >
                                    {generating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plane className="w-3 h-3" />}
                                    New Proposal ({p.name || 'Pilot'})
                                </Button>
                            ))}
                        </div>
                    )}

                    {proposals.some((p) => !p.policy_verdict?.allowed) && (
                        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs font-mono text-amber-400">
                            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                            Some proposals are blocked by policy. Review details before approving.
                        </div>
                    )}
                </div>

                {/* Sidebar: Account */}
                <div className="xl:col-span-1">
                    <AccountSummary />
                </div>
            </div>

            <GlassBoxTrade
                open={detailOpen}
                onOpenChange={setDetailOpen}
                proposalId={detailId}
                initialProposal={detailProposal}
            />
        </>
    );
}
