import React, { useEffect, useRef, memo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Calendar } from 'lucide-react';

const EarningsCalendarWidget = memo(({ theme = 'dark' }) => {
    const container = useRef(null);

    useEffect(() => {
        let isMounted = true;
        let scriptTag = null;

        // Cleanup function to remove the specific script and clear container
        const cleanup = () => {
            isMounted = false;
            if (scriptTag && document.body.contains(scriptTag)) {
                scriptTag.remove();
            }
            if (container.current) {
                container.current.innerHTML = '';
            }
        };

        // Reset container
        if (container.current) {
            container.current.innerHTML = '';
        }

        // Small delay to allow React strict mode to settle
        const timeoutId = setTimeout(() => {
            if (!isMounted || !container.current) return;

            const script = document.createElement("script");
            scriptTag = script;
            script.src = "https://s3.tradingview.com/external-embedding/embed-widget-events.js";
            script.type = "text/javascript";
            script.async = true;
            script.innerHTML = JSON.stringify({
                "colorTheme": theme,
                "isTransparent": true,
                "width": "100%",
                "height": "400",
                "locale": "en",
                "importanceFilter": "-1,0,1",
                "currencyFilter": "USD"
            });

            container.current.appendChild(script);
        }, 100);

        return () => {
            clearTimeout(timeoutId);
            cleanup();
        };
    }, [theme]);

    return (
        <Card className="rounded-xl dark:border-border/50 border-border shadow-md dark:bg-card/50 bg-card">
            <CardHeader className="pb-2 pt-3 px-4 border-b dark:border-border/20 border-border">
                <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-primary" />
                    Economic & Earnings Calendar
                </CardTitle>
            </CardHeader>
            <CardContent className="px-4 py-4">
                <div
                    className="tradingview-widget-container"
                    ref={container}
                    style={{ height: '400px', width: '100%' }}
                />
            </CardContent>
        </Card>
    );
});

export default EarningsCalendarWidget;
