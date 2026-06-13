import { Eye, X } from 'lucide-react';

/* A persistent "monitor list" of recently-focused securities — the terminal's
   running tape of what you're watching. Click a chip to re-focus + re-read it.
   Purely a navigation convenience; state lives in the parent (localStorage). */
export default function MonitorList({ tickers = [], active, onPick, onClear }) {
  if (!tickers.length) return null;
  return (
    <div className="flex items-center gap-2 font-mono text-xs" data-testid="monitor-list">
      <span className="flex items-center gap-1 text-muted-foreground/70 uppercase tracking-widest flex-shrink-0">
        <Eye className="w-3.5 h-3.5" aria-hidden="true" /> Monitor
      </span>
      <div className="flex items-center gap-1.5 flex-wrap">
        {tickers.map((t) => (
          <button
            key={t}
            onClick={() => onPick?.(t)}
            data-testid={`monitor-chip-${t}`}
            aria-current={t === active ? 'true' : undefined}
            className={
              'px-2 py-0.5 rounded border transition-colors ' +
              (t === active
                ? 'border-primary/50 bg-primary/10 text-primary'
                : 'border-border bg-card/40 text-muted-foreground hover:text-foreground hover:border-primary/30')
            }
          >
            {t}
          </button>
        ))}
      </div>
      <button
        onClick={onClear}
        className="ml-1 p-0.5 rounded text-muted-foreground/50 hover:text-loss hover:bg-loss/10 transition-colors flex-shrink-0"
        title="Clear monitor list"
        aria-label="Clear monitor list"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
}
