import { memo, useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const MEGA_CAPS = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA', 'BRK-B', 'LLY', 'TSM', 'AVGO'];
const LARGE_CAPS = ['V', 'JPM', 'UNH', 'WMT', 'MA', 'JNJ', 'PG', 'HD', 'ORCL', 'COST', 'BAC', 'CRM', 'NFLX', 'AMD', 'KO'];

function getBlockSize(symbol) {
    if (MEGA_CAPS.includes(symbol)) return 'col-span-2 row-span-2';
    if (LARGE_CAPS.includes(symbol)) return 'col-span-2 row-span-1';
    return 'col-span-1 row-span-1';
}

function getBlockColor(percent) {
    if (percent == null) return 'bg-muted text-foreground';
    // TradingView exact heatmap colors
    if (percent >= 3) return 'bg-[#089981] text-white shadow-inner';
    if (percent > 0) return 'bg-[#089981]/70 text-white hover:bg-[#089981]/90 shadow-inner';
    if (percent <= -3) return 'bg-[#F23645] text-white shadow-inner';
    if (percent < 0) return 'bg-[#F23645]/70 text-white hover:bg-[#F23645]/90 shadow-inner';
    return 'bg-muted text-foreground';
}

function HeatmapBlock({ stock }) {
    if (!stock) return null;
    const { symbol, change_percent, price } = stock;
    const isPositive = change_percent >= 0;

    return (
        <Link
            to={`/stock/${symbol}`}
            className={`${getBlockSize(symbol)} ${getBlockColor(change_percent)} p-1.5 flex flex-col items-center justify-center hover:scale-[1.02] hover:z-10 hover:shadow-lg transition-all duration-200 rounded shadow-sm overflow-hidden border border-background/20`}
        >
            <span className="font-mono text-sm sm:text-base font-bold tracking-wider w-full text-center drop-shadow-sm pt-0.5 leading-normal text-white">{symbol}</span>
            <div className="flex flex-col items-center mt-0.5 w-full text-center text-white">
                <span className="font-data text-[11px] sm:text-xs opacity-90 drop-shadow-sm">${price?.toFixed(2)}</span>
                <span className="font-data text-[10px] sm:text-[11px] font-bold opacity-100 drop-shadow-sm">
                    {isPositive ? '+' : ''}{change_percent?.toFixed(2)}%
                </span>
            </div>
        </Link>
    );
}

const TABS = ['ALL', 'TECH', 'INDUSTRIALS', 'FINANCIALS', 'ENERGY', 'HEALTHCARE', 'CONSUMER', 'REAL ESTATE', 'COMM', 'UTILITIES'];

const SECTOR_MAP = {
    'TECH': 'Technology',
    'INDUSTRIALS': 'Industrials',
    'FINANCIALS': 'Financials',
    'ENERGY': 'Energy',
    'HEALTHCARE': 'Healthcare',
    'CONSUMER': 'Consumer',
    'REAL ESTATE': 'Real Estate',
    'COMM': 'Communication',
    'UTILITIES': 'Utilities'
};

export default memo(function MarketHeatmap({ heatmapData }) {
    const [activeTab, setActiveTab] = useState('TECH');
    const [isFading, setIsFading] = useState(false);
    const [displayTab, setDisplayTab] = useState('TECH');

    useEffect(() => {
        setIsFading(false);
    }, [displayTab]);

    if (!heatmapData || Object.keys(heatmapData).length === 0) {
        return <div className="h-full min-h-[200px] w-full flex items-center justify-center text-xs font-mono text-muted-foreground">Loading Heatmap...</div>;
    }

    const handleTabChange = (tab) => {
        if (tab === activeTab) return;
        setActiveTab(tab);
        setIsFading(true);
        setTimeout(() => {
            setDisplayTab(tab);
        }, 150); // Matches fade out duration
    };

    const renderGrid = () => {
        if (displayTab === 'ALL') {
            return Object.entries(heatmapData).map(([sector, stocks]) => {
                if (!stocks || stocks.length === 0) return null;
                const topStocks = stocks.slice(0, 4);
                return (
                    <div key={sector} className="flex flex-col dark:bg-card/30 bg-white rounded-lg p-2 dark:border-border/30 border-border shadow-sm mb-3">
                        <h3 className="text-xs font-mono font-bold uppercase text-muted-foreground mb-2 px-1 tracking-wider">{sector}</h3>
                        <div className="grid grid-flow-row-dense grid-cols-2 sm:grid-cols-4 gap-1 auto-rows-[60px]">
                            {topStocks.map(stock => (
                                <HeatmapBlock key={stock.symbol} stock={stock} />
                            ))}
                        </div>
                    </div>
                );
            });
        } else {
            const mappedSector = SECTOR_MAP[displayTab];
            // Find the fuzzy matching sector from the API data
            const sectorKey = Object.keys(heatmapData).find(s => s.toLowerCase().includes(mappedSector.toLowerCase()));
            const stocks = sectorKey ? heatmapData[sectorKey] : [];
            
            if (!stocks || stocks.length === 0) {
                return <div className="p-4 text-center text-xs text-muted-foreground font-mono">No data for {mappedSector}</div>;
            }

            return (
                <div className="flex flex-col dark:bg-card/30 bg-white rounded-lg p-2 dark:border-border/30 border-border shadow-sm h-full">
                    <h3 className="text-xs font-mono font-bold uppercase text-muted-foreground mb-2 px-1 tracking-wider">{sectorKey}</h3>
                    <div className="grid grid-flow-row-dense grid-cols-3 sm:grid-cols-4 md:grid-cols-5 xl:grid-cols-6 gap-1 auto-rows-[60px]">
                        {stocks.map(stock => (
                            <HeatmapBlock key={stock.symbol} stock={stock} />
                        ))}
                    </div>
                </div>
            );
        }
    };

    return (
        <div className="flex flex-col h-full overflow-hidden dark:bg-card bg-white rounded-xl">
            {/* Tab Navigation */}
            <div className="flex gap-1.5 pb-3 overflow-x-auto no-scrollbar shrink-0 px-1 pt-1">
                {TABS.map(tab => {
                    const isActive = activeTab === tab;
                    return (
                        <button
                            key={tab}
                            onClick={() => handleTabChange(tab)}
                            className={`whitespace-nowrap px-3 py-1.5 text-[10px] uppercase tracking-wider font-mono rounded-[6px] transition-all duration-200 ${
                                isActive 
                                ? 'bg-[var(--color-accent)] text-black font-bold shadow-sm' 
                                : 'bg-transparent dark:text-[#666] text-[#444] border border-[rgba(255,255,255,0.1)] dark:border-[rgba(255,255,255,0.1)] hover:border-[rgba(255,255,255,0.3)]'
                            }`}
                        >
                            {tab}
                        </button>
                    )
                })}
            </div>

            {/* Heatmap Grid area with fade transition */}
            <div 
                className={`flex-1 overflow-y-auto pr-1 transition-opacity duration-150 ${isFading ? 'opacity-0' : 'opacity-100'}`}
                style={{ scrollbarWidth: 'thin' }}
            >
                {renderGrid()}
            </div>
        </div>
    );
});
