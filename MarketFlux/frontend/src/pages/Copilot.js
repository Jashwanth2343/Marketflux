import { lazy, Suspense } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plane, Wand2, ListChecks, Wallet } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';

const StrategyTerminal = lazy(() => import('@/components/StrategyTerminal'));
const TradingCopilotPanel = lazy(() => import('@/components/copilot/TradingCopilotPanel'));
const AccountSummary = lazy(() => import('@/components/copilot/AccountSummary'));

const tabs = [
    { value: 'copilot', label: 'Trading Copilot', icon: Plane },
    { value: 'studio', label: 'Strategy Studio', icon: Wand2 },
    { value: 'proposals', label: 'Proposals', icon: ListChecks },
    { value: 'portfolio', label: 'Paper Portfolio', icon: Wallet },
];

function LoadingSpinner() {
    return (
        <div className="flex h-64 items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
    );
}

export default function Copilot() {
    const [searchParams, setSearchParams] = useSearchParams();
    const activeTab = searchParams.get('tab') || 'copilot';

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
        <div className="min-h-screen bg-background p-4 md:p-6">
            <div className="mb-6">
                <h1 className="text-2xl font-bold font-mono tracking-tight text-foreground flex items-center gap-3">
                    <Plane className="w-7 h-7 text-primary" />
                    Trading Copilot
                </h1>
                <p className="text-sm text-muted-foreground mt-1 font-mono">
                    AI-powered strategy generation, trade proposals, and paper portfolio management
                </p>
            </div>

            <Tabs value={activeTab} onValueChange={handleTabChange}>
                <TabsList className="bg-white/5 border border-white/10 p-1 mb-6 flex-wrap h-auto gap-1">
                    {tabs.map(({ value, label, icon: Icon }) => (
                        <TabsTrigger
                            key={value}
                            value={value}
                            className="data-[state=active]:bg-primary/20 data-[state=active]:text-primary font-mono text-xs uppercase tracking-wider gap-2"
                        >
                            <Icon className="w-4 h-4" />
                            {label}
                        </TabsTrigger>
                    ))}
                </TabsList>

                <TabsContent value="copilot" className="mt-0">
                    <Suspense fallback={<LoadingSpinner />}>
                        <TradingCopilotPanel />
                    </Suspense>
                </TabsContent>
                <TabsContent value="studio" className="mt-0">
                    <Suspense fallback={<LoadingSpinner />}>
                        <StrategyTerminal embedded />
                    </Suspense>
                </TabsContent>
                <TabsContent value="proposals" className="mt-0">
                    <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 text-center max-w-lg mx-auto">
                        <ListChecks className="w-12 h-12 text-primary mx-auto mb-4" />
                        <h3 className="text-lg font-semibold text-foreground mb-2">Trade proposals</h3>
                        <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto">
                            Pending proposals, consent, and generation controls live under{' '}
                            <span className="font-mono text-foreground">Trading Copilot</span>.
                        </p>
                        <Button
                            type="button"
                            variant="outline"
                            className="font-mono text-xs uppercase tracking-wider"
                            onClick={() => handleTabChange('copilot')}
                        >
                            Open Trading Copilot
                        </Button>
                    </div>
                </TabsContent>
                <TabsContent value="portfolio" className="mt-0">
                    <Suspense fallback={<LoadingSpinner />}>
                        <div className="max-w-2xl">
                            <AccountSummary />
                        </div>
                    </Suspense>
                </TabsContent>
            </Tabs>
        </div>
    );
}
