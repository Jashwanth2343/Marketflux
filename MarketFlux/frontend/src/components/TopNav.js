import { useState, useRef, useEffect, memo } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Activity, LayoutDashboard, Briefcase, Sun, Moon, LogIn, LogOut, User, Menu, X, Brain, Plane, Trophy, FlaskConical, BookMarked } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import SearchBar from '@/components/SearchBar';

const navItems = [
    { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/intelligence', icon: Brain, label: 'Intelligence' },
    { path: '/copilot', icon: Plane, label: 'Copilot' },
    { path: '/ledger', icon: BookMarked, label: 'Ledger' },
    { path: '/backtest', icon: FlaskConical, label: 'Backtest' },
    { path: '/portfolio', icon: Briefcase, label: 'Portfolio' },
    { path: '/leaderboard', icon: Trophy, label: 'Leaderboard' },
];

const TickerTapeWidget = memo(({ isDark }) => {
  const container = useRef(null);
  useEffect(() => {
    const el = container.current;
    if (!el) return;
    el.innerHTML = '';
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js';
    script.async = true;
    script.innerHTML = JSON.stringify({
      symbols: [
        { proName: 'FOREXCOM:SPXUSD', title: 'S&P 500' },
        { proName: 'FOREXCOM:NSXUSD', title: 'Nasdaq 100' },
        { proName: 'FX_IDC:EURUSD', title: 'EUR/USD' },
        { proName: 'BITSTAMP:BTCUSD', title: 'Bitcoin' },
        { proName: 'BITSTAMP:ETHUSD', title: 'Ethereum' },
      ],
      showSymbolLogo: true,
      isTransparent: true,
      displayMode: 'adaptive',
      colorTheme: isDark ? 'dark' : 'light',
      locale: 'en',
    });
    el.appendChild(script);
  }, [isDark]);

  return (
    <div
      className="tradingview-widget-container border-b border-border/40 bg-background/50 w-full overflow-hidden"
      style={{ height: '46px' }}
    >
      <div className="tradingview-widget-container__widget" ref={container} />
    </div>
  );
});

function MarketStatusDot() {
  const [isOpen, setIsOpen] = useState(null);
  useEffect(() => {
    const now = new Date();
    const et = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
    const day = et.getDay();
    const h = et.getHours() + et.getMinutes() / 60;
    setIsOpen(day >= 1 && day <= 5 && h >= 9.5 && h < 16);
  }, []);
  if (isOpen === null) return null;
  return (
    <div className={`hidden lg:flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-mono uppercase tracking-wider border ${
      isOpen
        ? 'border-primary/20 bg-primary/5 text-primary'
        : 'border-border bg-muted/40 text-muted-foreground'
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${isOpen ? 'bg-primary pulse-live' : 'bg-muted-foreground/40'}`} />
      {isOpen ? 'Live' : 'Closed'}
    </div>
  );
}

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
    <div className="w-full flex flex-col z-50 sticky top-0 backdrop-blur-md border-b border-border/60 bg-background/90">
      <TickerTapeWidget isDark={isDark} />

      {/* Main Nav */}
      <header className="flex items-center justify-between px-4 py-2.5 gap-3" data-testid="app-header">

        {/* Left: Logo */}
        <div className="flex items-center gap-5 flex-shrink-0">
          <Link to="/" className="flex items-center gap-2 group" data-testid="logo-link">
            <Activity className="w-5 h-5 text-primary" />
            <span className="font-mono text-base font-bold tracking-tight text-primary hidden sm:inline">
              MARKET FLUX
            </span>
          </Link>
          <MarketStatusDot />
        </div>

        {/* Center: Desktop Nav */}
        <nav className="hidden lg:flex items-center gap-0.5 flex-1 justify-center">
          {navItems.map(({ path, icon: Icon, label }) => {
            const active = isActive(path);
            return (
              <Link
                key={path}
                to={path}
                className={`relative flex items-center gap-1.5 px-3 py-2 text-[11px] font-mono uppercase tracking-wider rounded-md transition-all duration-150 ${
                  active
                    ? 'text-primary bg-primary/10'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
                {active && (
                  <span className="absolute bottom-0 left-2 right-2 h-px bg-primary rounded-full" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Right: Search + Theme + Auth */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Search — desktop */}
          <div className="hidden md:flex w-44 lg:w-52 xl:w-64">
            <SearchBar />
          </div>

          {/* Theme toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            className="w-8 h-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-all"
          >
            {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </Button>

          {/* Auth — desktop */}
          <div className="hidden lg:flex items-center gap-2">
            {user ? (
              <>
                <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-primary/5 border border-primary/10">
                  <div className="w-5 h-5 rounded-full bg-primary/15 flex items-center justify-center">
                    <User className="w-3 h-3 text-primary" />
                  </div>
                  <span className="text-[10px] font-mono text-muted-foreground max-w-[100px] truncate">
                    {user.name || user.email}
                  </span>
                </div>
                <Button
                  data-testid="logout-btn"
                  variant="ghost"
                  size="sm"
                  onClick={logout}
                  className="text-[10px] font-mono uppercase tracking-wider gap-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all px-2.5 h-8"
                >
                  <LogOut className="w-3 h-3" /> Logout
                </Button>
              </>
            ) : (
              <>
                <Link to="/auth">
                  <Button
                    data-testid="login-nav-btn"
                    variant="ghost"
                    size="sm"
                    className="text-[10px] font-mono uppercase tracking-wider gap-1.5 text-muted-foreground hover:text-primary hover:bg-primary/5 transition-all px-3 h-8"
                  >
                    <LogIn className="w-3 h-3" /> Login
                  </Button>
                </Link>
                <Button
                  data-testid="google-login-sidebar-btn"
                  size="sm"
                  onClick={loginWithGoogle}
                  className="text-[10px] font-mono uppercase tracking-wider h-8 px-3 transition-all duration-200"
                >
                  Sign In
                </Button>
              </>
            )}
          </div>

          {/* Mobile menu toggle */}
          <Button
            data-testid="mobile-menu-toggle"
            variant="ghost"
            size="icon"
            className="lg:hidden w-8 h-8 rounded-md text-primary hover:bg-primary/10"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </Button>
        </div>
      </header>

      {/* Mobile Dropdown */}
      {mobileOpen && (
        <div className="lg:hidden absolute top-full left-0 w-full border-b border-border/60 p-4 flex flex-col gap-3 shadow-2xl z-50 bg-background/95 backdrop-blur-xl">
          <div className="w-full">
            <SearchBar />
          </div>
          <nav className="grid grid-cols-2 gap-1">
            {navItems.map(({ path, icon: Icon, label }) => (
              <Link
                key={path}
                to={path}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-2.5 px-3 py-2.5 text-xs font-mono uppercase tracking-wider rounded-md transition-colors border ${
                  isActive(path)
                    ? 'bg-primary/10 text-primary border-primary/20'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground border-transparent'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </Link>
            ))}
          </nav>
          <div className="pt-3 border-t border-border flex flex-col gap-2">
            {user ? (
              <>
                <div className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-primary/5">
                  <User className="w-3.5 h-3.5 text-primary" />
                  <span className="text-xs font-mono text-muted-foreground truncate">{user.name || user.email}</span>
                </div>
                <Button
                  variant="outline"
                  className="w-full text-xs font-mono text-destructive border-destructive/20 hover:bg-destructive/10 gap-2 justify-start"
                  onClick={() => { logout(); setMobileOpen(false); }}
                >
                  <LogOut className="w-3.5 h-3.5" /> Logout
                </Button>
              </>
            ) : (
              <>
                <Link to="/auth" onClick={() => setMobileOpen(false)}>
                  <Button variant="outline" className="w-full text-xs font-mono text-muted-foreground border-border gap-2 justify-start">
                    <LogIn className="w-3.5 h-3.5" /> Login with Email
                  </Button>
                </Link>
                <Button
                  className="w-full text-xs font-mono gap-2 justify-start"
                  onClick={() => { loginWithGoogle(); setMobileOpen(false); }}
                >
                  Continue with Google
                </Button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
