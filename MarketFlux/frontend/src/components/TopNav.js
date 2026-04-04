import { useState, useRef, useEffect, memo } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Activity, LayoutDashboard, Newspaper, Search, Briefcase, TerminalSquare, Sun, Moon, LogIn, LogOut, User, Menu, X, Brain, Globe, Shield, BookOpenText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import SearchBar from '@/components/SearchBar';

const navItems = [
    { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/news', icon: Newspaper, label: 'News Feed' },
    { path: '/screener', icon: Search, label: 'AI Screener' },
    { path: '/research', icon: Brain, label: 'Research' },
    { path: '/macro', icon: Globe, label: 'Macro' },
    { path: '/risk', icon: Shield, label: 'Risk' },
    { path: '/portfolio', icon: Briefcase, label: 'Portfolio' },
    { path: '/theses', icon: BookOpenText, label: 'Theses' },
    { path: '/fund-os', icon: TerminalSquare, label: 'Fund OS' },
];

const TickerTapeWidget = memo(({ isDark }) => {
    const container = useRef(null);

    useEffect(() => {
        const currentContainer = container.current;
        if (currentContainer) {
            currentContainer.innerHTML = '';
            const script = document.createElement('script');
            script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js';
            script.type = 'text/javascript';
            script.async = true;
            script.innerHTML = JSON.stringify({
                "symbols": [
                    { "proName": "FOREXCOM:SPXUSD", "title": "S&P 500" },
                    { "proName": "FOREXCOM:NSXUSD", "title": "Nasdaq 100" },
                    { "proName": "FX_IDC:EURUSD", "title": "EUR/USD" },
                    { "proName": "BITSTAMP:BTCUSD", "title": "Bitcoin" },
                    { "proName": "BITSTAMP:ETHUSD", "title": "Ethereum" }
                ],
                "showSymbolLogo": true,
                "isTransparent": true,
                "displayMode": "adaptive",
                "colorTheme": isDark ? "dark" : "light",
                "locale": "en"
            });
            currentContainer.appendChild(script);
        }
    }, [isDark]);

    return (
        <div className="tradingview-widget-container border-b border-border bg-background w-full overflow-hidden" style={{ height: "46px" }}>
            <div className="tradingview-widget-container__widget" ref={container}></div>
        </div>
    );
});

export default function TopNav() {
    const location = useLocation();
    const { user, logout, loginWithGoogle } = useAuth();
    const { isDark, toggleTheme } = useTheme();
    const [mobileOpen, setMobileOpen] = useState(false);

    const isActive = (path) => {
        if (path === '/') return location.pathname === '/';
        return location.pathname === path || location.pathname.startsWith(`${path}/`);
    };

    return (
        <div className="w-full flex flex-col z-50 sticky top-0 dark:bg-card/80 bg-card backdrop-blur-md border-b border-border">
            <TickerTapeWidget isDark={isDark} />

            {/* Main Nav */}
            <header className="flex items-center justify-between px-4 py-3 gap-4" data-testid="app-header">
                {/* Left: Logo & Links (Desktop) */}
                <div className="flex items-center gap-6">
                    <Link to="/" className="flex items-center gap-2" data-testid="logo-link">
                        <Activity className="w-6 h-6 text-primary" />
                        <span className="font-mono text-lg font-bold tracking-tight text-primary glow-text-green hidden sm:inline">
                            MARKET FLUX
                        </span>
                    </Link>

                    {/* Desktop Nav Links */}
                    <nav className="hidden lg:flex items-center gap-1">
                        {navItems.map(({ path, icon: Icon, label }) => (
                            <Link
                                key={path}
                                to={path}
                                className={`flex items-center gap-2 px-3 py-2 text-xs font-mono uppercase tracking-wider rounded-md transition-colors ${
                                    isActive(path) 
                                        ? 'bg-primary/10 text-primary font-bold' 
                                        : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                                }`}
                            >
                                <Icon className="w-4 h-4" />
                                {label}
                            </Link>
                        ))}
                    </nav>
                </div>

                {/* Center: Search */}
                <div className="flex-1 max-w-xl hidden md:flex justify-center">
                    <SearchBar />
                </div>

                {/* Right: Theme Toggle & Auth */}
                <div className="flex items-center gap-2 lg:gap-4">
                    <Button variant="ghost" size="icon" onClick={toggleTheme} className="text-muted-foreground hover:text-primary transition-colors">
                        {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                    </Button>

                    <div className="hidden lg:flex items-center gap-3">
                        {user ? (
                            <div className="flex items-center gap-4">
                                <div className="flex items-center gap-2">
                                    <User className="w-4 h-4 text-primary" />
                                    <span className="text-xs font-mono text-muted-foreground max-w-[120px] truncate">
                                        {user.name || user.email}
                                    </span>
                                </div>
                                <Button data-testid="logout-btn" variant="outline" size="sm" onClick={logout} className="text-xs font-mono uppercase tracking-wider items-center gap-2 hover:bg-destructive hover:text-destructive-foreground">
                                    <LogOut className="w-3 h-3" /> Logout
                                </Button>
                            </div>
                        ) : (
                            <div className="flex items-center gap-2">
                                <Link to="/auth">
                                    <Button data-testid="login-nav-btn" variant="ghost" size="sm" className="text-xs font-mono uppercase tracking-wider items-center gap-2 text-muted-foreground hover:text-primary">
                                        <LogIn className="w-3 h-3" /> Login
                                    </Button>
                                </Link>
                                <Button data-testid="google-login-sidebar-btn" variant="outline" size="sm" onClick={loginWithGoogle} className="text-xs font-mono uppercase tracking-wider items-center gap-2 border-primary/30 text-primary hover:bg-primary hover:text-black">
                                    Google Login
                                </Button>
                            </div>
                        )}
                    </div>

                    {/* Mobile Menu Toggle */}
                    <Button data-testid="mobile-menu-toggle" variant="ghost" size="icon" className="lg:hidden text-primary" onClick={() => setMobileOpen(!mobileOpen)}>
                        {mobileOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
                    </Button>
                </div>
            </header>

            {/* Mobile Menu Dropdown & Search */}
            {mobileOpen && (
                <div className="lg:hidden absolute top-full left-0 w-full bg-card border-b border-border p-4 flex flex-col gap-4 shadow-xl">
                    <div className="w-full">
                        <SearchBar />
                    </div>
                    <nav className="flex flex-col gap-2">
                        {navItems.map(({ path, icon: Icon, label }) => (
                            <Link
                                key={path}
                                to={path}
                                onClick={() => setMobileOpen(false)}
                                className={`flex items-center gap-3 px-3 py-3 text-sm font-mono uppercase tracking-wider rounded-sm transition-colors ${isActive(path) ? 'bg-primary text-primary-foreground font-bold' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                                    }`}
                            >
                                <Icon className="w-4 h-4" />
                                {label}
                            </Link>
                        ))}
                    </nav>
                    <div className="pt-4 border-t border-border flex flex-col gap-3">
                        {user ? (
                            <>
                                <div className="flex items-center gap-2 px-2 pb-2">
                                    <User className="w-4 h-4 text-primary" />
                                    <span className="text-xs font-mono text-muted-foreground truncate">{user.name || user.email}</span>
                                </div>
                                <Button variant="outline" className="w-full justify-start text-xs font-mono text-destructive border-destructive/30 hover:bg-destructive hover:text-destructive-foreground gap-2" onClick={() => { logout(); setMobileOpen(false); }}>
                                    <LogOut className="w-4 h-4" /> Logout
                                </Button>
                            </>
                        ) : (
                            <>
                                <Link to="/auth" onClick={() => setMobileOpen(false)}>
                                    <Button variant="ghost" className="w-full justify-start text-xs font-mono gap-2 text-muted-foreground hover:text-primary">
                                        <LogIn className="w-4 h-4" /> Login
                                    </Button>
                                </Link>
                                <Button variant="outline" className="w-full justify-start text-xs font-mono text-primary border-primary/30 hover:bg-primary hover:text-black gap-2" onClick={() => { loginWithGoogle(); setMobileOpen(false); }}>
                                    Google Login
                                </Button>
                            </>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
