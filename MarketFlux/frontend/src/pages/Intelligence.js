import { useSearchParams } from 'react-router-dom';
import { Brain, Newspaper, Search, Globe, BookOpenText } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import NewsFeed from '@/pages/NewsFeed';
import AIScreener from '@/pages/AIScreener';
import ResearchCenter from '@/pages/ResearchCenter';
import MacroDashboard from '@/pages/MacroDashboard';
import Theses from '@/pages/Theses';

const tabs = [
    { value: 'research', label: 'Research', icon: Brain },
    { value: 'news', label: 'News', icon: Newspaper },
    { value: 'screener', label: 'Screener', icon: Search },
    { value: 'macro', label: 'Macro', icon: Globe },
    { value: 'theses', label: 'Theses', icon: BookOpenText },
];

export default function Intelligence() {
    const [searchParams, setSearchParams] = useSearchParams();
    const activeTab = searchParams.get('tab') || 'research';

    const handleTabChange = (value) => {
        setSearchParams({ tab: value }, { replace: true });
    };

    return (
        <div className="min-h-screen bg-background p-4 md:p-6">
            <div className="mb-6">
                <h1 className="text-2xl font-bold font-mono tracking-tight text-foreground flex items-center gap-3">
                    <Brain className="w-7 h-7 text-primary" />
                    Intelligence Hub
                </h1>
                <p className="text-sm text-muted-foreground mt-1 font-mono">
                    Research, news, screening, macro analysis, and investment theses
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

                <TabsContent value="research" className="mt-0">
                    <ResearchCenter embedded />
                </TabsContent>
                <TabsContent value="news" className="mt-0">
                    <NewsFeed embedded />
                </TabsContent>
                <TabsContent value="screener" className="mt-0">
                    <AIScreener embedded />
                </TabsContent>
                <TabsContent value="macro" className="mt-0">
                    <MacroDashboard embedded />
                </TabsContent>
                <TabsContent value="theses" className="mt-0">
                    <Theses embedded />
                </TabsContent>
            </Tabs>
        </div>
    );
}
