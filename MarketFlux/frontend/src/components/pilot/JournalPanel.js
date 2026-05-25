import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Loader2, RefreshCw, BookOpen, Sparkles } from 'lucide-react';

import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import api from '@/lib/api';

function formatDate(iso) {
  if (!iso) return '';
  try {
    return new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

function StatTile({ label, value }) {
  return (
    <div className="flex flex-col gap-0.5 px-3 py-2 rounded bg-muted/40 border border-border min-w-[80px]">
      <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-sm font-semibold text-foreground tabular-nums">{value}</div>
    </div>
  );
}

function AttributionBar({ name, score, max }) {
  const pct = max > 0 ? Math.min(100, Math.abs(score) / max * 100) : 0;
  const positive = score >= 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-16 truncate text-muted-foreground capitalize">{name}</span>
      <div className="flex-1 h-2 bg-muted/40 rounded overflow-hidden relative">
        <div
          className={`absolute top-0 ${positive ? 'left-1/2' : 'right-1/2'} h-full ${
            positive ? 'bg-green-500/70' : 'bg-red-500/70'
          }`}
          style={{ width: `${pct / 2}%` }}
        />
        <div className="absolute top-0 left-1/2 w-px h-full bg-border" />
      </div>
      <span className={`w-12 text-right font-mono tabular-nums ${positive ? 'text-green-500' : 'text-red-500'}`}>
        {score >= 0 ? '+' : ''}{score.toFixed(1)}
      </span>
    </div>
  );
}

function JournalEntry({ entry }) {
  if (!entry) return null;
  const stats = entry.stats || {};
  const attribution = stats.attribution || {};
  const attrEntries = Object.entries(attribution);
  const attrMax = Math.max(1, ...attrEntries.map(([, v]) => Math.abs(v || 0)));

  return (
    <article className="rounded-lg border border-border bg-card p-4 flex flex-col gap-3">
      <header className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-semibold">{formatDate(entry.date)}</span>
          {entry.source === 'llm' ? (
            <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/30">
              <Sparkles className="w-3 h-3" /> ai
            </span>
          ) : (
            <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border">
              template
            </span>
          )}
        </div>
      </header>

      <div className="flex flex-wrap gap-2">
        <StatTile label="Today" value={stats.proposals_today ?? 0} />
        <StatTile label="Filled" value={stats.executed ?? 0} />
        <StatTile label="Rejected" value={stats.rejected ?? 0} />
        <StatTile label="Expired" value={stats.expired ?? 0} />
        {Number.isFinite(stats.avg_conviction_executed) ? (
          <StatTile label="Conv. avg" value={stats.avg_conviction_executed.toFixed(1)} />
        ) : null}
      </div>

      {entry.summary ? (
        <p className="text-sm leading-relaxed whitespace-pre-wrap text-foreground">{entry.summary}</p>
      ) : null}

      {entry.lessons ? (
        <p className="text-xs leading-relaxed text-muted-foreground italic">
          <span className="font-mono uppercase tracking-wider not-italic text-muted-foreground/80 mr-1">
            lessons:
          </span>
          {entry.lessons}
        </p>
      ) : null}

      {attrEntries.length > 0 ? (
        <div className="flex flex-col gap-1">
          <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            attribution (signal categories on executed buys)
          </div>
          {attrEntries.map(([name, score]) => (
            <AttributionBar key={name} name={name} score={score} max={attrMax} />
          ))}
        </div>
      ) : null}

      {entry.tomorrows_watchlist?.length ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            watching:
          </span>
          {entry.tomorrows_watchlist.map((t) => (
            <span
              key={t}
              className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-foreground border border-border"
            >
              {t}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
}

export function JournalPanel({ open, onOpenChange, personality }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  const fetchEntries = async () => {
    if (!personality?.id) return;
    setLoading(true);
    try {
      const res = await api.get(
        `/pilot/personalities/${personality.id}/journal`,
        { params: { limit: 30 } }
      );
      setEntries(res?.data?.items || []);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message;
      toast.error(`Couldn't load journal. ${String(detail)}`);
    } finally {
      setLoading(false);
    }
  };

  const generateToday = async () => {
    if (!personality?.id) return;
    setGenerating(true);
    try {
      const res = await api.post(
        `/pilot/personalities/${personality.id}/journal/generate`,
        {}
      );
      if (res?.data?.item) {
        toast.success(`${personality.name} wrote today's entry.`);
        await fetchEntries();
      }
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message;
      toast.error(`Couldn't generate entry. ${String(detail)}`);
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    if (open) fetchEntries();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, personality?.id]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <BookOpen className="w-4 h-4" />
            {personality?.name || 'Personality'} journal
          </SheetTitle>
          <SheetDescription>
            Candid end-of-day notes from this AI. Paper trading only · not investment advice.
          </SheetDescription>
        </SheetHeader>

        <div className="mt-4 flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={fetchEntries}
            disabled={loading}
            className="gap-1 font-mono text-xs uppercase tracking-wider"
          >
            {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            Refresh
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={generateToday}
            disabled={generating}
            className="gap-1 font-mono text-xs uppercase tracking-wider"
          >
            {generating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
            Write today
          </Button>
        </div>

        <div className="mt-4 flex flex-col gap-3 pb-12">
          {loading && entries.length === 0 ? (
            <div className="text-center text-xs text-muted-foreground py-8">Loading…</div>
          ) : entries.length === 0 ? (
            <div className="text-center text-xs text-muted-foreground py-8">
              No journal entries yet. Run a few proposals and they'll appear here
              after the nightly batch.
            </div>
          ) : (
            entries.map((entry) => <JournalEntry key={entry.id} entry={entry} />)
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

export default JournalPanel;
