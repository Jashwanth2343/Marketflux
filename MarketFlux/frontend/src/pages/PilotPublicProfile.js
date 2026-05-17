import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Loader2, Plane, Trophy, BookOpen, Sparkles } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import api from '@/lib/api';

const GLYPHS = {
  circle: (color) => (
    <span
      className="inline-block w-5 h-5 rounded-full"
      style={{ backgroundColor: color, boxShadow: `0 0 10px ${color}88` }}
    />
  ),
  triangle: (color) => (
    <span
      className="inline-block"
      style={{
        width: 0,
        height: 0,
        borderLeft: '10px solid transparent',
        borderRight: '10px solid transparent',
        borderBottom: `18px solid ${color}`,
        filter: `drop-shadow(0 0 6px ${color}88)`,
      }}
    />
  ),
  square: (color) => (
    <span
      className="inline-block w-5 h-5 rounded-sm"
      style={{ backgroundColor: color, boxShadow: `0 0 10px ${color}88` }}
    />
  ),
  hexagon: (color) => (
    <span
      className="inline-block w-5 h-5"
      style={{
        backgroundColor: color,
        clipPath: 'polygon(25% 5%, 75% 5%, 100% 50%, 75% 95%, 25% 95%, 0% 50%)',
        boxShadow: `0 0 10px ${color}88`,
      }}
    />
  ),
};

function Glyph({ shape, color }) {
  const render = GLYPHS[shape] || GLYPHS.circle;
  return render(color || '#22c55e');
}

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

export default function PilotPublicProfile() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const res = await api.get(`/pilot/public/${encodeURIComponent(slug)}`);
        if (!cancelled) setData(res?.data);
      } catch (err) {
        if (!cancelled) {
          setError(err?.response?.data?.detail || err?.message || 'Failed to load profile.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [slug]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data?.personality) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Card>
          <CardContent className="p-6 flex flex-col items-center gap-3">
            <div className="text-sm font-semibold">Personality not found</div>
            <p className="text-xs text-muted-foreground max-w-sm text-center">
              {String(error || 'Either this Pilot is private, or the link is wrong.')}
            </p>
            <Link to="/leaderboard">
              <Button size="sm" variant="outline" className="gap-1 font-mono text-xs uppercase tracking-wider">
                <Trophy className="w-3 h-3" />
                Open Leaderboard
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const p = data.personality;
  const accent = p.accent_color || '#22c55e';
  const journals = data.journals || [];
  const weights = p.signal_weights || {};

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/40 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <Link to="/leaderboard">
              <Button size="sm" variant="ghost" className="gap-1 font-mono text-xs uppercase tracking-wider">
                <ArrowLeft className="w-3 h-3" />
                Leaderboard
              </Button>
            </Link>
          </div>
          <Link to="/copilot">
            <Button size="sm" variant="outline" className="gap-1 font-mono text-xs uppercase tracking-wider">
              <Plane className="w-3 h-3" />
              Build your own
            </Button>
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 flex flex-col gap-6">
        {/* Hero */}
        <section
          className="rounded-xl border border-border bg-card p-6 flex flex-col gap-4"
          style={{ borderTop: `4px solid ${accent}` }}
        >
          <div className="flex items-center gap-3">
            <Glyph shape={p.avatar_glyph} color={accent} />
            <div>
              <h1 className="text-2xl font-semibold" style={{ color: accent }}>
                {p.name}
              </h1>
              <div className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
                {p.cadence || 'daily'} cadence · v{p.version || 1} · paper trading
              </div>
            </div>
          </div>
          <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap">{p.mandate}</p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
            <div className="px-3 py-2 rounded bg-muted/40 border border-border">
              <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">universe</div>
              <div className="text-sm font-semibold tabular-nums">{p.universe?.length || 0}</div>
            </div>
            <div className="px-3 py-2 rounded bg-muted/40 border border-border">
              <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">capital</div>
              <div className="text-sm font-semibold tabular-nums">
                ${Number(p.initial_capital_usd || 0).toLocaleString()}
              </div>
            </div>
            <div className="px-3 py-2 rounded bg-muted/40 border border-border">
              <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">max pos %</div>
              <div className="text-sm font-semibold tabular-nums">
                {(p.risk_policy?.max_position_pct || 0).toFixed(0)}%
              </div>
            </div>
            <div className="px-3 py-2 rounded bg-muted/40 border border-border">
              <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">max DD</div>
              <div className="text-sm font-semibold tabular-nums">
                {(p.risk_policy?.max_drawdown_pct || 0).toFixed(0)}%
              </div>
            </div>
          </div>

          {/* Signal weights */}
          {Object.keys(weights).length > 0 ? (
            <div className="flex flex-col gap-1 pt-2">
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                signal weights
              </div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(weights).map(([name, w]) => (
                  <span
                    key={name}
                    className="text-[11px] font-mono px-2 py-0.5 rounded bg-muted text-foreground border border-border capitalize"
                  >
                    {name}: {(Number(w) * 100).toFixed(0)}%
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </section>

        {/* Journal feed */}
        <section className="flex flex-col gap-3">
          <header className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-muted-foreground" />
            <h2 className="text-lg font-semibold">Recent journal</h2>
            <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
              past {journals.length} entr{journals.length === 1 ? 'y' : 'ies'}
            </span>
          </header>

          {journals.length === 0 ? (
            <Card>
              <CardContent className="px-4 py-10 text-center text-xs text-muted-foreground">
                {p.name} hasn't published a journal entry yet. Check back after the next nightly batch.
              </CardContent>
            </Card>
          ) : (
            journals.map((entry) => (
              <article
                key={entry.id}
                className="rounded-lg border border-border bg-card p-4 flex flex-col gap-2"
              >
                <header className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold">{formatDate(entry.date)}</span>
                    {entry.source === 'llm' ? (
                      <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/30">
                        <Sparkles className="w-3 h-3" /> ai
                      </span>
                    ) : null}
                  </div>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                    {entry.stats?.executed ?? 0} filled · {entry.stats?.rejected ?? 0} rejected
                  </div>
                </header>
                {entry.summary ? (
                  <p className="text-sm leading-relaxed whitespace-pre-wrap text-foreground">
                    {entry.summary}
                  </p>
                ) : null}
                {entry.lessons ? (
                  <p className="text-xs italic text-muted-foreground">{entry.lessons}</p>
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
            ))
          )}
        </section>

        <p className="text-[11px] text-muted-foreground text-center pt-2 pb-8">
          {data.disclaimer || 'Paper trading only. Not investment advice.'}
        </p>
      </main>
    </div>
  );
}
