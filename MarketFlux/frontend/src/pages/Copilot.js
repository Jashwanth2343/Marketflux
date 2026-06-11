import { lazy, Suspense } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Bot,
  BriefcaseBusiness,
  Cpu,
  ListChecks,
  Plane,
  ShieldCheck,
  Wand2,
  Wallet,
} from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';

const CopilotAgent = lazy(() => import('@/components/copilot/CopilotAgent'));
const StrategyTerminal = lazy(() => import('@/components/StrategyTerminal'));
const StandingAgents = lazy(() => import('@/components/copilot/StandingAgents'));
const AccountSummary = lazy(() => import('@/components/copilot/AccountSummary'));

const tabs = [
  {
    value: 'copilot',
    label: 'Agent',
    longLabel: 'Copilot Agent',
    description: 'Conversational trading assistant',
    icon: Bot,
  },
  {
    value: 'studio',
    label: 'Studio',
    longLabel: 'Strategy Studio',
    description: 'Build and hand off strategies',
    icon: Wand2,
  },
  {
    value: 'proposals',
    label: 'Auto-Pilot',
    longLabel: 'Auto-Pilot',
    description: 'Standing agents and proposals',
    icon: ListChecks,
  },
  {
    value: 'portfolio',
    label: 'Portfolio',
    longLabel: 'Paper Portfolio',
    description: 'Account, cash, positions',
    icon: Wallet,
  },
];

function LoadingSpinner() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/10 border-b-primary" />
    </div>
  );
}

function TrustBadge({ icon: Icon, label }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.035] px-3 py-1 text-[11px] font-mono uppercase tracking-[0.14em] text-muted-foreground shadow-sm shadow-black/20 backdrop-blur">
      <Icon className="h-3.5 w-3.5 text-primary" />
      {label}
    </span>
  );
}

export default function Copilot() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'copilot';
  const activeMeta = tabs.find((tab) => tab.value === activeTab) || tabs[0];
  const ActiveIcon = activeMeta.icon;

  const handleTabChange = (value) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', value);
        return next;
      },
      { replace: true },
    );
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="border-b border-white/[0.06] bg-[linear-gradient(180deg,rgba(255,255,255,0.045),rgba(255,255,255,0.015))]">
        <div className="px-4 py-4 md:px-6">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="min-w-0">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-2xl border border-primary/25 bg-primary/[0.08] shadow-[0_0_28px_-10px_hsl(var(--primary)/0.9)]">
                  <Plane className="h-5 w-5 text-primary" />
                </span>
                <TrustBadge icon={ShieldCheck} label="Paper trading" />
                <TrustBadge icon={Cpu} label="Tool-using agent" />
              </div>
              <h1 className="text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
                Trading Copilot
              </h1>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
                Open a conversation, inspect every action, and keep the older autonomous proposal workflow nearby when you need it.
              </p>
            </div>

            <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full xl:w-auto">
              <TabsList className="grid h-auto w-full grid-cols-2 gap-1 rounded-2xl border border-white/10 bg-white/[0.035] p-1 shadow-lg shadow-black/20 backdrop-blur xl:flex xl:w-auto">
                {tabs.map(({ value, label, longLabel, icon: Icon }) => (
                  <TabsTrigger
                    key={value}
                    value={value}
                    title={longLabel}
                    className="group h-11 rounded-xl px-3 text-xs font-medium text-muted-foreground transition-all data-[state=active]:bg-primary data-[state=active]:text-black data-[state=active]:shadow-[0_10px_30px_-14px_hsl(var(--primary)/0.95)] md:px-4"
                  >
                    <Icon className="mr-2 h-4 w-4" />
                    <span className="hidden sm:inline">{longLabel}</span>
                    <span className="sm:hidden">{label}</span>
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
        </div>
      </div>

      <main className="px-4 py-5 md:px-6 md:py-6">
        {/* The Agent tab is a self-contained, centered chat canvas — it carries its
            own status row, so the per-tab sub-header would be redundant there. */}
        {activeTab !== 'copilot' && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <ActiveIcon className="h-4 w-4 text-primary" />
                {activeMeta.longLabel}
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">{activeMeta.description}</p>
            </div>
          </div>
        )}

        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsContent value="copilot" className="mt-0">
            <Suspense fallback={<LoadingSpinner />}>
              <CopilotAgent />
            </Suspense>
          </TabsContent>

          <TabsContent value="studio" className="mt-0">
            <Suspense fallback={<LoadingSpinner />}>
              <StrategyTerminal embedded />
            </Suspense>
          </TabsContent>

          <TabsContent value="proposals" className="mt-0">
            <Suspense fallback={<LoadingSpinner />}>
              <StandingAgents />
            </Suspense>
          </TabsContent>

          <TabsContent value="portfolio" className="mt-0">
            <Suspense fallback={<LoadingSpinner />}>
              <div className="max-w-2xl rounded-2xl border border-white/10 bg-white/[0.025] p-5 shadow-xl shadow-black/25 backdrop-blur">
                <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-foreground">
                  <BriefcaseBusiness className="h-4 w-4 text-primary" />
                  Paper Account
                </div>
                <AccountSummary source="copilot" />
              </div>
            </Suspense>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
