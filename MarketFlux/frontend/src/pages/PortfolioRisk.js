import { useSearchParams } from 'react-router-dom';
import { Briefcase, Shield } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import Portfolio from '@/pages/Portfolio';
import RiskConsole from '@/pages/RiskConsole';

const tabs = [
    { value: 'holdings', label: 'Holdings', icon: Briefcase },
    { value: 'risk', label: 'Risk Analytics', icon: Shield },
];

export default function PortfolioRisk() {
    const [searchParams, setSearchParams] = useSearchParams();
    const activeTab = searchParams.get('tab') || 'holdings';

    const handleTabChange = (value) => {
        setSearchParams({ tab: value }, { replace: true });
    };

    return (
        <div className="min-h-screen bg-background p-4 md:p-6">
            <div className="mb-6">
                <h1 className="text-2xl font-bold font-mono tracking-tight text-foreground flex items-center gap-3">
                    <Briefcase className="w-7 h-7 text-primary" />
                    Portfolio & Risk
                </h1>
                <p className="text-sm text-muted-foreground mt-1 font-mono">
                    Holdings management and risk analytics
                </p>
            </div>

            <Tabs value={activeTab} onValueChange={handleTabChange}>
                <TabsList className="bg-white/5 border border-white/10 p-1 mb-6 gap-1">
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

                <TabsContent value="holdings" className="mt-0">
                    <Portfolio embedded />
                </TabsContent>
                <TabsContent value="risk" className="mt-0">
                    <RiskConsole embedded />
                </TabsContent>
            </Tabs>
        </div>
    );
}
