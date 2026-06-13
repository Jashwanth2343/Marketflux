import { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Brain, X, Keyboard } from 'lucide-react';
import { cn } from '@/lib/utils';
import NewsFeed from '@/pages/NewsFeed';
import AIScreener from '@/pages/AIScreener';
import ResearchCenter from '@/pages/ResearchCenter';
import MacroDashboard from '@/pages/MacroDashboard';
import Theses from '@/pages/Theses';
import { FUNCTIONS, TAB_VALUES, functionByTab } from '@/components/intelligence/functions';
import TerminalStatusBar from '@/components/intelligence/TerminalStatusBar';
import CommandLine from '@/components/intelligence/CommandLine';
import ReadPanel from '@/components/intelligence/ReadPanel';

const PAGES = {
  research: ResearchCenter,
  news: NewsFeed,
  screener: AIScreener,
  macro: MacroDashboard,
  theses: Theses,
};

function HelpOverlay({ onClose }) {
  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-black/60 backdrop-blur-sm p-4 pt-[10vh]" onClick={onClose} data-testid="terminal-help">
      <div className="w-full max-w-lg bg-card border border-border rounded-xl shadow-2xl shadow-black/40 overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <span className="flex items-center gap-2 font-mono text-sm font-bold text-foreground"><Keyboard className="w-4 h-4 text-primary" /> Terminal commands</span>
          <button onClick={onClose} className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted/60" aria-label="Close help"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3 font-mono text-xs">
          <div>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/70 mb-1.5">Functions</p>
            <div className="grid grid-cols-1 gap-1">
              {FUNCTIONS.map((f) => (
                <div key={f.code} className="flex items-center gap-2">
                  <kbd className="w-8 text-center text-primary font-bold">{f.code}</kbd>
                  <kbd className="text-muted-foreground/60">{f.n}</kbd>
                  <span className="text-foreground">{f.label}</span>
                  <span className="text-muted-foreground truncate">— {f.desc}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="border-t border-border pt-3 space-y-1.5">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/70 mb-1.5">Syntax</p>
            <div className="flex gap-2"><kbd className="text-primary w-28">NVDA</kbd><span className="text-muted-foreground">focus a security + AI read</span></div>
            <div className="flex gap-2"><kbd className="text-primary w-28">why TSLA</kbd><span className="text-muted-foreground">grounded AI tape-read, with sources</span></div>
            <div className="flex gap-2"><kbd className="text-primary w-28">semis under 15 PE</kbd><span className="text-muted-foreground">natural-language screen</span></div>
            <div className="flex gap-2"><kbd className="text-primary w-28">ask … / @…</kbd><span className="text-muted-foreground">hand off to the trading copilot</span></div>
          </div>
          <div className="border-t border-border pt-3 space-y-1.5">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground/70 mb-1.5">Keyboard</p>
            <div className="flex gap-2"><kbd className="text-primary w-28">/</kbd><span className="text-muted-foreground">focus the command line</span></div>
            <div className="flex gap-2"><kbd className="text-primary w-28">1 – 5</kbd><span className="text-muted-foreground">jump to a function</span></div>
            <div className="flex gap-2"><kbd className="text-primary w-28">↑ ↓ · ↵ · esc</kbd><span className="text-muted-foreground">navigate · run · clear</span></div>
            <div className="flex gap-2"><kbd className="text-primary w-28">?</kbd><span className="text-muted-foreground">this help</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Intelligence() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const requested = searchParams.get('tab');
  const activeTab = TAB_VALUES.includes(requested) ? requested : 'research';

  const [focused, setFocused] = useState(null);
  const [read, setRead] = useState(null);
  const [showHelp, setShowHelp] = useState(false);

  const selectTab = useCallback((tab) => {
    setSearchParams({ tab }, { replace: true });
  }, [setSearchParams]);

  const askCopilot = useCallback((text) => {
    sessionStorage.setItem('copilot_ask', text);
    navigate('/copilot');
  }, [navigate]);

  const handleFunction = useCallback((tab) => {
    if (tab === '__help__') { setShowHelp(true); return; }
    selectTab(tab);
  }, [selectTab]);

  const handleRead = useCallback((ticker) => {
    setFocused(ticker);
    setRead(ticker);
  }, []);

  const handleScreen = useCallback((query) => {
    sessionStorage.setItem('mf_screener_query', query);
    window.dispatchEvent(new CustomEvent('mf:screener-query', { detail: query }));
    selectTab('screener');
  }, [selectTab]);

  // Number hotkeys (1–5) jump functions; "?" opens help. Ignored while typing.
  useEffect(() => {
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = (e.target?.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || e.target?.isContentEditable) return;
      if (e.key === '?' || (e.key === '/' && e.shiftKey)) { e.preventDefault(); setShowHelp((v) => !v); return; }
      if (e.key === 'Escape') { setShowHelp(false); return; }
      const fn = FUNCTIONS.find((f) => String(f.n) === e.key);
      if (fn) { e.preventDefault(); selectTab(fn.tab); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectTab]);

  const ActivePage = PAGES[activeTab] || ResearchCenter;
  const activeFn = functionByTab(activeTab);

  return (
    <div className="min-h-screen bg-background p-4 md:p-6">
      <header className="mb-4">
        <h1 className="text-2xl font-bold font-mono tracking-tight text-foreground flex items-center gap-3">
          <Brain className="w-7 h-7 text-primary" />
          Intelligence Terminal
        </h1>
        <p className="text-sm text-muted-foreground mt-1 font-mono">
          Command-driven market intelligence — research, news, screening, macro &amp; theses, AI-native.
        </p>
      </header>

      <div className="space-y-4">
        <TerminalStatusBar
          focused={focused}
          onRead={() => focused && handleRead(focused)}
          onDetail={() => focused && navigate(`/stock/${focused}`)}
          onAsk={() => focused && askCopilot(`What's your read on ${focused} right now?`)}
          onClearFocus={() => { setFocused(null); setRead(null); }}
        />

        <CommandLine
          onFunction={handleFunction}
          onRead={handleRead}
          onAsk={askCopilot}
          onScreen={handleScreen}
          onFocus={setFocused}
        />

        {read && <ReadPanel ticker={read} onClose={() => setRead(null)} />}

        {/* Function rail — numbered, keyboard-addressable (1–5) */}
        <nav className="flex flex-wrap gap-1.5" aria-label="Intelligence functions" data-testid="function-rail">
          {FUNCTIONS.map((f) => {
            const active = f.tab === activeTab;
            const Icon = f.icon;
            return (
              <button
                key={f.tab}
                onClick={() => selectTab(f.tab)}
                aria-current={active ? 'page' : undefined}
                data-testid={`fn-tab-${f.tab}`}
                className={cn(
                  'group flex items-center gap-2 px-3 py-2 rounded-md border font-mono text-xs uppercase tracking-wider transition-colors',
                  active
                    ? 'border-primary/50 bg-primary/10 text-primary'
                    : 'border-border bg-card/40 text-muted-foreground hover:text-foreground hover:border-primary/30',
                )}
              >
                <kbd className={cn('text-[10px] px-1 rounded border', active ? 'border-primary/40 text-primary' : 'border-border text-muted-foreground/60')}>{f.n}</kbd>
                <Icon className="w-4 h-4" />
                <span className="hidden sm:inline">{f.label}</span>
                <span className="sm:hidden">{f.code}</span>
              </button>
            );
          })}
          <button
            onClick={() => setShowHelp(true)}
            data-testid="fn-help"
            className="ml-auto flex items-center gap-1.5 px-3 py-2 rounded-md border border-border bg-card/40 text-muted-foreground hover:text-foreground hover:border-primary/30 font-mono text-xs uppercase tracking-wider transition-colors"
            title="Command help (?)"
          >
            <Keyboard className="w-4 h-4" />
            <span className="hidden sm:inline">Help</span>
          </button>
        </nav>

        <main aria-label={activeFn?.label || 'Intelligence'} data-testid={`fn-panel-${activeTab}`}>
          <ActivePage embedded />
        </main>
      </div>

      {showHelp && <HelpOverlay onClose={() => setShowHelp(false)} />}
    </div>
  );
}
