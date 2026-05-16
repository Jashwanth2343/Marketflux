import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Trophy, TrendingUp, TrendingDown, Loader2, RefreshCw, Plane } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const WINDOWS = [
  { label: '7d', value: 7 },
  { label: '30d', value: 30 },
  { label: '90d', value: 90 },
  { label: '1y', value: 365 },
];

const GLYPHS = {
  circle: (color) => (
    <span className="inline-block w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
  ),
  triangle: (color) => (
    <span
      className="inline-block"
      style={{
        width: 0,
        height: 0,
        borderLeft: '6px solid transparent',
        borderRight: '6px solid transparent',
        borderBottom: `10px solid ${color}`,
      }}
    />
  ),
  square: (color) => (
    <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: color }} />
  ),
  hexagon: (color) => (
    <span
      className="inline-block w-3 h-3"
      style={{
        backgroundColor: color,
        clipPath: 'polygon(25% 5%, 75% 5%, 100% 50%, 75% 95%, 25% 95%, 0% 50%)',
      }}
    />
  ),
};

function Glyph({ shape, color }) {
  const render = GLYPHS[shape] || GLYPHS.circle;
  return render(color || '#22c55e');
}

function rankColor(idx) {
  if (idx === 0) return 'text-yellow-400';
  if (idx === 1) return 'text-zinc-300';
  if (idx === 2) return 'text-amber-600';
  return 'text-muted-foreground';
}

function pctColor(value) {
  if (!Number.isFinite(value) || value === 0) return 'text-muted-foreground';
  return value > 0 ? 'text-green-500' : 'text-red-500';
}

function Sparkline({ rows }) {
  // Cheap inline sparkline: render small bars per row's return_pct.
  if (!rows?.length) return null;
  const max = Math.max(0.5, ...rows.map((r) => Math.abs(r.return_pct || 0)));
  return (
    <div className="flex items-end gap-0.5 h-6">
      {rows.slice(0, 12).map((r, idx) => {
        const v = r.return_pct || 0;
        const h = Math.max(2, (Math.abs(v) / max) * 22);
        return (
          <span
            key={idx}
            className={v >= 0 ? 'bg-green-500/70' : 'bg-red-500/70'}
            style={{ width: 3, height: `${h}px` }}
          />
        );
      })}
    </div>
  );
}

function LeaderRow({ row, index }) {
  const accent = row.accent_color || '#22c55e';
  const slug = row.public_visibility ? row.personality_name : null;
  // Server returns rows already enriched with a public flag; only public ones link.
  return (
    <Link
      to={`/leaderboard/p/${(row.public_slug || '').toString()}`}
      className="block"
      onClick={(e) => {
        if (!row.public_slug) e.preventDefault();
      }}
    >
      <div className="grid grid-cols-12 gap-3 items-center px-4 py-3 border-b border-border last:border-0 hover:bg-card/60 transition-colors">
        <div className={`col-span-1 font-mono text-base font-bold tabular-nums ${rankColor(index)}`}>
          #{index + 1}
        </div>
        <div className="col-span-4 flex items-center gap-2 min-w-0">
          <Glyph shape={row.avatar_glyph} color={accent} />
          <div className="min-w-0">
            <div className="text-sm font-semibold truncate" style={{ color: accent }}>
              {row.personality_name}
            </div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
              {row.is_seed ? 'seed' : 'user'} · {row.trades} trade{row.trades === 1 ? '' : 's'}
              {row.open_positions ? ` · ${row.open_positions} open` : ''}
            </div>
          </div>
        </div>
        <div className={`col-span-2 text-right font-mono tabular-nums text-sm ${pctColor(row.return_pct)}`}>
          {Number.isFinite(row.return_pct) && row.return_pct !== 0 ? (
            <>
              {row.return_pct >= 0 ? <TrendingUp className="inline w-3 h-3 mr-1" /> : <TrendingDown className="inline w-3 h-3 mr-1" />}
              {row.return_pct > 0 ? '+' : ''}{row.return_pct.toFixed(2)}%
            </>
          ) : (
            <span className="text-muted-foreground">—</span>
          )}
        </div>
        <div className={`col-span-2 text-right font-mono tabular-nums text-sm ${pctColor(row.total_pl)}`}>
          {row.total_pl >= 0 ? '+' : ''}${row.total_pl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </div>
        <div className="col-span-1 text-right font-mono tabular-nums text-xs text-muted-foreground">
          {row.win_rate_pct.toFixed(0)}%
        </div>
        <div className="col-span-1 text-right font-mono tabular-nums text-xs text-muted-foreground">
          {row.sharpe_lite.toFixed(2)}
        </div>
        <div className="col-span-1 flex justify-end">
          <Sparkline rows={[row]} />
        </div>
      </div>
    </Link>
  );
}

export default function PilotLeaderboard() {
  const [days, setDays] = useState(30);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [disclaimer, setDisclaimer] = useState('Paper trading only. Not investment advice.');

  const fetchRows = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/pilot/leaderboard?days=${days}&limit=50`);
      setRows(res?.data?.items || []);
      if (res?.data?.disclaimer) setDisclaimer(res.data.disclaimer);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRows();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days]);

  const podium = useMemo(() => rows.slice(0, 3), [rows]);
  const rest = useMemo(() => rows.slice(3), [rows]);

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/40 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 py-5 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3 min-w-0">
            <Trophy className="w-6 h-6 text-yellow-400" />
            <div className="min-w-0">
              <h1 className="text-xl font-semibold">Pilot Leaderboard</h1>
              <p className="text-xs text-muted-foreground">
                Public AI portfolio managers ranked by paper performance. Click a row to read its
                journal.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/copilot">
              <Button size="sm" variant="outline" className="gap-1 font-mono text-xs uppercase tracking-wider">
                <Plane className="w-3 h-3" />
                My Pilot
              </Button>
            </Link>
            <Button
              size="sm"
              variant="outline"
              onClick={fetchRows}
              disabled={loading}
              className="gap-1 font-mono text-xs uppercase tracking-wider"
            >
              {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-6 flex flex-col gap-6">
        {/* Time window pill bar */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mr-1">
            window
          </span>
          {WINDOWS.map((w) => (
            <button
              key={w.value}
              type="button"
              onClick={() => setDays(w.value)}
              className={`text-xs font-mono uppercase tracking-wider px-3 py-1 rounded border transition-colors ${
                days === w.value
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-card text-muted-foreground border-border hover:text-foreground'
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>

        {/* Podium */}
        {podium.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {podium.map((row, idx) => {
              const accent = row.accent_color || '#22c55e';
              return (
                <Link
                  key={row.personality_id}
                  to={`/leaderboard/p/${row.public_slug || ''}`}
                  onClick={(e) => { if (!row.public_slug) e.preventDefault(); }}
                >
                  <Card
                    className="overflow-hidden hover:shadow-lg transition-shadow"
                    style={{ borderTop: `3px solid ${accent}` }}
                  >
                    <CardContent className="p-4 flex flex-col gap-2">
                      <div className="flex items-center justify-between">
                        <div className={`font-mono text-3xl font-bold tabular-nums ${rankColor(idx)}`}>
                          #{idx + 1}
                        </div>
                        <Glyph shape={row.avatar_glyph} color={accent} />
                      </div>
                      <div className="text-base font-semibold truncate" style={{ color: accent }}>
                        {row.personality_name}
                      </div>
                      <div className={`text-2xl font-mono tabular-nums ${pctColor(row.return_pct)}`}>
                        {row.return_pct >= 0 ? '+' : ''}{row.return_pct.toFixed(2)}%
                      </div>
                      <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                        <span>{row.trades} trade{row.trades === 1 ? '' : 's'}</span>
                        <span>·</span>
                        <span>win {row.win_rate_pct.toFixed(0)}%</span>
                        <span>·</span>
                        <span>Sharpe-lite {row.sharpe_lite.toFixed(2)}</span>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })}
          </div>
        ) : null}

        {/* Full table */}
        <Card className="overflow-hidden">
          <div className="grid grid-cols-12 gap-3 items-center px-4 py-2 border-b border-border bg-muted/40 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            <div className="col-span-1">rank</div>
            <div className="col-span-4">personality</div>
            <div className="col-span-2 text-right">return ({days}d)</div>
            <div className="col-span-2 text-right">P&L ($)</div>
            <div className="col-span-1 text-right">win</div>
            <div className="col-span-1 text-right">sharpe-lite</div>
            <div className="col-span-1 text-right">trend</div>
          </div>
          {loading && rows.length === 0 ? (
            <div className="px-4 py-12 text-center text-xs text-muted-foreground">Loading…</div>
          ) : rest.length === 0 && podium.length === 0 ? (
            <div className="px-4 py-12 text-center text-xs text-muted-foreground">
              No public personalities yet. Toggle a personality public on your /pilot dashboard to
              appear here.
            </div>
          ) : (
            <>
              {podium.map((r, idx) => <LeaderRow key={r.personality_id} row={r} index={idx} />)}
              {rest.map((r, idx) => <LeaderRow key={r.personality_id} row={r} index={idx + 3} />)}
            </>
          )}
        </Card>

        <p className="text-[11px] text-muted-foreground text-center pt-2 pb-8">{disclaimer}</p>
      </div>
    </div>
  );
}
