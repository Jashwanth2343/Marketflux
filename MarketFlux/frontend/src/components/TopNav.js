import { useState, useRef, useEffect, memo } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Activity, LayoutDashboard, Briefcase, Sun, Moon, LogIn, LogOut, User,
  Menu, X, Brain, Sparkles, Search, Command,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import SearchBar from '@/components/SearchBar';

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/copilot?tab=proposals', match: '/copilot', icon: Sparkles, label: 'Agents' },
  { path: '/intelligence?tab=screener', match: '/intelligence', matchQuery: 'screener', icon: Search, label: 'Screener' },
  { path: '/intelligence?tab=research', match: '/intelligence', matchQuery: 'research', icon: Brain, label: 'Research' },
  { path: '/portfolio', icon: Briefcase, label: 'Portfolio' },
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
      className="tradingview-widget-container border-b border-border/40 bg-background/60 w-full overflow-hidden"
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
    <div
      className={`hidden lg:flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-medium tracking-wide border ${
        isOpen
          ? 'border-[color:var(--mf-bull-border)] bg-[color:var(--mf-bull-bg)] text-[color:var(--mf-bull-strong)]'
          : 'border-border bg-muted/40 text-muted-foreground'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${isOpen ? 'bg-[color:var(--mf-bull)] pulse-live' : 'bg-muted-foreground/40'}`} />
      {isOpen ? 'Live' : 'Closed'}
    </div>
  );
}

export default function TopNav() {
  const location = useLocation();
  const { user, logout, loginWithGoogle } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (item) => {
    const base = item.match || item.path.split('?')[0];
    const pathMatch = base === '/' ? location.pathname === '/' : location.pathname.startsWith(base);
    if (!pathMatch) return false;
    if (item.matchQuery) {
      const tab = new URLSearchParams(location.search).get('tab');
      return tab === item.matchQuery;
    }
    return true;
  };

  const openTerminal = () => window.dispatchEvent(new Event('marketflux:open-terminal'));

  return (
    <div
      className="w-full flex flex-col z-50 sticky top-0 backdrop-blur-md border-b border-border/60"
      style={{ background: 'color-mix(in srgb, hsl(var(--background)) 90%, transparent)' }}
    >
      <TickerTapeWidget isDark={isDark} />

      {/* Main Nav */}
      <header className="flex items-center justify-between px-4 py-2.5 gap-3" data-testid="app-header">
        {/* Left: Wordmark */}
        <div className="flex items-center gap-5 flex-shrink-0">
          <Link to="/" className="flex items-center gap-2 group" data-testid="logo-link">
            <span
              className="inline-flex items-center justify-center w-7 h-7 rounded-md text-[color:var(--mf-accent-fg)]"
              style={{ background: 'var(--mf-accent)' }}
            >
              <Activity className="w-4 h-4" strokeWidth={2.4} />
            </span>
            <span className="font-semibold text-[15px] tracking-tight text-foreground hidden sm:inline">
              Market<span style={{ color: 'var(--mf-accent-strong)' }}>Flux</span>
            </span>
          </Link>
          <MarketStatusDot />
        </div>

        {/* Center: Desktop Nav */}
        <nav className="hidden lg:flex items-center gap-1 flex-1 justify-center">
          {navItems.map((item) => {
            const { path, icon: Icon, label } = item;
            const active = isActive(item);
            return (
              <Link
                key={label}
                to={path}
                className={`relative flex items-center gap-1.5 px-3 py-1.5 text-[12.5px] font-medium rounded-md transition-colors duration-150 ${
                  active
                    ? 'text-foreground bg-[color:var(--mf-accent-bg)]'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${active ? 'text-[color:var(--mf-accent-strong)]' : ''}`} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Right: Search + Ask FluxAI + Theme + Auth */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Search — desktop */}
          <div className="hidden md:flex w-44 lg:w-52 xl:w-64">
            <SearchBar />
          </div>

          {/* Ask FluxAI — opens the side panel */}
          <button
            type="button"
            onClick={openTerminal}
            className="hidden md:inline-flex items-center gap-1.5 h-8 px-3 rounded-md text-xs font-semibold transition-colors"
            style={{
              background: 'var(--mf-accent)',
              color: 'var(--mf-accent-fg)',
              boxShadow: '0 0 0 1px var(--mf-accent-border)',
            }}
            data-testid="ask-fluxai-btn"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Ask FluxAI
          </button>

          {/* Theme toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            className="w-8 h-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50"
            data-testid="theme-toggle"
          >
            {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </Button>

          {/* Auth — desktop */}
          <div className="hidden lg:flex items-center gap-2">
            {user ? (
              <>
                <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-muted/40 border border-border">
                  <div
                    className="w-5 h-5 rounded-full flex items-center justify-center"
                    style={{ background: 'var(--mf-accent-bg)' }}
                  >
                    <User className="w-3 h-3" style={{ color: 'var(--mf-accent-strong)' }} />
                  </div>
                  <span className="text-[10.5px] font-medium text-muted-foreground max-w-[100px] truncate">
                    {user.name || user.email}
                  </span>
                </div>
                <Button
                  data-testid="logout-btn"
                  variant="ghost"
                  size="sm"
                  onClick={logout}
                  className="text-[10.5px] font-medium gap-1.5 text-muted-foreground hover:text-[color:var(--mf-bear-strong)] hover:bg-[color:var(--mf-bear-bg)] transition-colors px-2.5 h-8"
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
                    className="text-[10.5px] font-medium gap-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors px-3 h-8"
                  >
                    <LogIn className="w-3 h-3" /> Login
                  </Button>
                </Link>
                <Button
                  data-testid="google-login-sidebar-btn"
                  size="sm"
                  onClick={loginWithGoogle}
                  className="text-[10.5px] font-semibold h-8 px-3 transition-colors"
                  style={{ background: 'var(--mf-accent)', color: 'var(--mf-accent-fg)' }}
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
            className="lg:hidden w-8 h-8 rounded-md text-foreground hover:bg-muted/50"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </Button>
        </div>
      </header>

      {/* Mobile Dropdown */}
      {mobileOpen && (
        <div
          className="lg:hidden absolute top-full left-0 w-full border-b border-border/60 p-4 flex flex-col gap-3 shadow-2xl z-50"
          style={{ background: 'color-mix(in srgb, hsl(var(--background)) 96%, transparent)', backdropFilter: 'blur(20px)' }}
        >
          <div className="w-full">
            <SearchBar />
          </div>
          <nav className="grid grid-cols-2 gap-1">
            {navItems.map((item) => {
              const { path, icon: Icon, label } = item;
              return (
                <Link
                  key={label}
                  to={path}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center gap-2.5 px-3 py-2.5 text-xs font-medium rounded-md transition-colors ${
                    isActive(item)
                      ? 'bg-[color:var(--mf-accent-bg)] text-foreground border border-[color:var(--mf-accent-border)]'
                      : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground border border-transparent'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {label}
                </Link>
              );
            })}
          </nav>
          <div className="pt-3 border-t border-border flex flex-col gap-2">
            <button
              onClick={() => { openTerminal(); setMobileOpen(false); }}
              className="w-full inline-flex items-center justify-center gap-2 h-9 rounded-md text-xs font-semibold"
              style={{ background: 'var(--mf-accent)', color: 'var(--mf-accent-fg)' }}
            >
              <Sparkles className="w-3.5 h-3.5" /> Ask FluxAI
            </button>
            {user ? (
              <>
                <div className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-muted/40">
                  <User className="w-3.5 h-3.5" style={{ color: 'var(--mf-accent-strong)' }} />
                  <span className="text-xs font-medium text-muted-foreground truncate">{user.name || user.email}</span>
                </div>
                <Button
                  variant="outline"
                  className="w-full text-xs text-[color:var(--mf-bear-strong)] border-[color:var(--mf-bear-border)] hover:bg-[color:var(--mf-bear-bg)] gap-2 justify-start"
                  onClick={() => { logout(); setMobileOpen(false); }}
                >
                  <LogOut className="w-3.5 h-3.5" /> Logout
                </Button>
              </>
            ) : (
              <>
                <Link to="/auth" onClick={() => setMobileOpen(false)}>
                  <Button variant="outline" className="w-full text-xs text-muted-foreground border-border gap-2 justify-start">
                    <LogIn className="w-3.5 h-3.5" /> Login with Email
                  </Button>
                </Link>
                <Button
                  className="w-full text-xs gap-2 justify-start"
                  style={{ background: 'var(--mf-accent)', color: 'var(--mf-accent-fg)' }}
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
