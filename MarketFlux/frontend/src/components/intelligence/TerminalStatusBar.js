import { useEffect, useState, useCallback } from 'react';
import { Activity, Zap, ExternalLink, MessageCircle, X } from 'lucide-react';
import { cn } from '@/lib/utils';

/* Dense, always-on terminal status strip: live ET clock, US-session state, and
   the currently-focused security with one-keystroke actions. Self-contained —
   market state is derived client-side from the America/New_York wall clock
   (regular session 09:30–16:00 ET, Mon–Fri; holidays not modeled). */

function nyParts(date) {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    weekday: 'short', hour12: false,
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
  return fmt.formatToParts(date).reduce((acc, p) => { acc[p.type] = p.value; return acc; }, {});
}

function sessionState(date) {
  const p = nyParts(date);
  const hour = Number(p.hour) % 24; // Intl can emit '24' at midnight
  const mins = hour * 60 + Number(p.minute);
  const isWeekday = !['Sat', 'Sun'].includes(p.weekday);
  const clock = `${String(hour).padStart(2, '0')}:${p.minute}:${p.second}`;
  if (!isWeekday) return { code: 'CLOSED', label: 'Weekend', tone: 'closed', clock };
  if (mins >= 570 && mins < 960) return { code: 'OPEN', label: 'Regular · closes 16:00 ET', tone: 'open', clock };
  if (mins >= 240 && mins < 570) return { code: 'PRE', label: 'Pre-market · opens 09:30 ET', tone: 'pre', clock };
  if (mins >= 960 && mins < 1200) return { code: 'AFT', label: 'After-hours · closed 16:00 ET', tone: 'pre', clock };
  return { code: 'CLOSED', label: 'Opens 09:30 ET', tone: 'closed', clock };
}

const TONE = {
  open: 'text-gain border-gain/40 bg-gain/10',
  pre: 'text-primary border-primary/40 bg-primary/10',
  closed: 'text-muted-foreground border-border bg-muted/40',
};

export default function TerminalStatusBar({ focused, onRead, onDetail, onAsk, onClearFocus }) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const s = sessionState(now);
  const action = useCallback((fn) => (e) => { e.stopPropagation(); fn?.(); }, []);

  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-2 border border-border bg-card/60 rounded-lg px-3 py-2 font-mono text-xs"
      data-testid="terminal-status-bar"
      role="status"
      aria-live="polite"
    >
      <span className="flex items-center gap-1.5 text-primary font-bold tracking-widest uppercase">
        <Activity className="w-3.5 h-3.5" aria-hidden="true" />
        MarketFlux Terminal
        <span className="ml-0.5 inline-block w-[7px] h-[14px] bg-primary animate-pulse" aria-hidden="true" />
      </span>

      <span className={cn('flex items-center gap-2 rounded-full border px-2.5 py-0.5 uppercase tracking-wide', TONE[s.tone])}>
        <span className="font-bold">{s.code}</span>
        <span className="opacity-70 normal-case tracking-normal hidden sm:inline">{s.label}</span>
      </span>

      <span className="text-muted-foreground tabular-nums" aria-label="New York time">
        {s.clock} <span className="opacity-60">ET</span>
      </span>

      <div className="flex-1" />

      {focused ? (
        <div className="flex items-center gap-1.5" data-testid="focused-security">
          <span className="text-muted-foreground/70 uppercase tracking-wide hidden md:inline">Focus</span>
          <span className="font-bold text-foreground bg-primary/10 border border-primary/30 rounded px-2 py-0.5">{focused}</span>
          <button onClick={action(onRead)} className="flex items-center gap-1 px-1.5 py-0.5 rounded text-primary hover:bg-primary/10 transition-colors" title="AI tape read" data-testid="focus-read">
            <Zap className="w-3 h-3" />READ
          </button>
          <button onClick={action(onDetail)} className="flex items-center gap-1 px-1.5 py-0.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors" title="Open security detail" data-testid="focus-detail">
            <ExternalLink className="w-3 h-3" />DETAIL
          </button>
          <button onClick={action(onAsk)} className="flex items-center gap-1 px-1.5 py-0.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors" title="Ask the copilot about this name" data-testid="focus-ask">
            <MessageCircle className="w-3 h-3" />ASK
          </button>
          <button onClick={action(onClearFocus)} className="p-0.5 rounded text-muted-foreground/60 hover:text-loss hover:bg-loss/10 transition-colors" title="Clear focus" aria-label="Clear focused security">
            <X className="w-3 h-3" />
          </button>
        </div>
      ) : (
        <span className="text-muted-foreground/50 hidden md:inline">
          type a ticker, a function code, or a question — <span className="text-primary">/</span> to command
        </span>
      )}
    </div>
  );
}
