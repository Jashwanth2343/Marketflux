import { useEffect, useState, useRef } from 'react';
import { TrendingUp, TrendingDown, Loader2 } from 'lucide-react';
import api from '@/lib/api';
import { cn } from '@/lib/utils';

/* Dense "security loaded" header for the focused name — hard data + an inline
   sparkline, the terminal counterpart to ReadPanel's AI narrative. Fetches
   GET /market/stock/{t} (quote) and /market/chart/{t} (sparkline). Abortable. */

const TICKER_RE = /^[A-Z][A-Z.\-^]{0,5}$/;

const num = (v) => (v == null || Number.isNaN(Number(v)) ? null : Number(v));
const px = (v) => (num(v) == null ? '—' : num(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
function compact(v, money) {
  const n = num(v);
  if (n == null) return '—';
  const p = money ? '$' : '';
  const a = Math.abs(n);
  if (a >= 1e12) return `${p}${(n / 1e12).toFixed(2)}T`;
  if (a >= 1e9) return `${p}${(n / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${p}${(n / 1e6).toFixed(2)}M`;
  if (a >= 1e3) return `${p}${(n / 1e3).toFixed(1)}K`;
  return `${p}${n.toLocaleString('en-US')}`;
}

function Sparkline({ closes }) {
  if (!Array.isArray(closes) || closes.length < 2) return null;
  const W = 132, H = 38, pad = 2;
  const lo = Math.min(...closes), hi = Math.max(...closes);
  const span = hi - lo || 1;
  const pts = closes.map((c, i) => {
    const x = pad + (i * (W - pad * 2)) / (closes.length - 1);
    const y = pad + (H - pad * 2) * (1 - (c - lo) / span);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const up = closes[closes.length - 1] >= closes[0];
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className={up ? 'text-gain' : 'text-loss'} aria-hidden="true">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function Stat({ label, value }) {
  return (
    <div className="flex flex-col">
      <span className="text-[9px] uppercase tracking-widest text-muted-foreground/60">{label}</span>
      <span className="text-xs text-foreground tabular-nums">{value}</span>
    </div>
  );
}

export default function SecurityHeader({ ticker }) {
  const [quote, setQuote] = useState({ status: 'idle' });
  const [closes, setCloses] = useState(null);
  const abortRef = useRef(null);

  useEffect(() => {
    if (!ticker) return;
    const t = String(ticker).toUpperCase();
    if (!TICKER_RE.test(t)) { setQuote({ status: 'error' }); return; }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setQuote({ status: 'loading' });
    setCloses(null);

    api.get(`/market/stock/${encodeURIComponent(t)}`, { signal: controller.signal })
      .then(({ data }) => setQuote({ status: 'done', data }))
      .catch((err) => { if (!controller.signal.aborted) setQuote({ status: 'error' }); });

    api.get(`/market/chart/${encodeURIComponent(t)}?period=1mo&interval=1d`, { signal: controller.signal })
      .then(({ data }) => {
        const series = (data?.data || []).map((p) => num(p.close)).filter((c) => c != null);
        setCloses(series);
      })
      .catch(() => { /* sparkline is optional */ });

    return () => controller.abort();
  }, [ticker]);

  if (!ticker) return null;
  const t = String(ticker).toUpperCase();
  const { status, data } = quote;

  if (status === 'loading' || status === 'idle') {
    return (
      <div className="border border-border bg-card rounded-lg p-3 flex items-center gap-2 text-xs font-mono text-muted-foreground" data-testid="security-header">
        <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" /> Loading {t}…
      </div>
    );
  }
  if (status === 'error') {
    return (
      <div className="border border-border bg-card rounded-lg p-3 text-xs font-mono text-muted-foreground" data-testid="security-header">
        {t} — quote unavailable.
      </div>
    );
  }

  const up = num(data?.change_percent) != null && num(data.change_percent) >= 0;
  return (
    <div className="border border-border bg-card rounded-lg p-3 font-mono" data-testid="security-header">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <div className="flex items-baseline gap-2 min-w-0">
          <span className="text-lg font-bold text-foreground">{t}</span>
          <span className="text-xs text-muted-foreground truncate max-w-[200px]">{data?.name || ''}</span>
        </div>

        <div className="flex items-baseline gap-2">
          <span className="text-lg font-bold text-foreground tabular-nums">${px(data?.price)}</span>
          {num(data?.change_percent) != null && (
            <span className={cn('flex items-center gap-1 text-sm', up ? 'text-gain' : 'text-loss')}>
              {up ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
              {num(data?.change) != null && <span className="tabular-nums">{up ? '+' : ''}{px(data.change)}</span>}
              <span className="tabular-nums">({up ? '+' : ''}{num(data.change_percent).toFixed(2)}%)</span>
            </span>
          )}
        </div>

        <Sparkline closes={closes} />

        {data?.sector && (
          <span className="text-[10px] uppercase tracking-wide text-primary border border-primary/30 bg-primary/10 rounded px-2 py-0.5">{data.sector}</span>
        )}
      </div>

      <div className="grid grid-cols-3 sm:grid-cols-6 gap-x-4 gap-y-2 mt-3 pt-3 border-t border-border">
        <Stat label="Day" value={`${px(data?.day_low)}–${px(data?.day_high)}`} />
        <Stat label="52W" value={`${px(data?.fifty_two_week_low)}–${px(data?.fifty_two_week_high)}`} />
        <Stat label="Vol" value={compact(data?.volume, false)} />
        <Stat label="Mkt Cap" value={compact(data?.market_cap, true)} />
        <Stat label="P/E" value={num(data?.pe_ratio) != null ? num(data.pe_ratio).toFixed(1) : '—'} />
        <Stat label="Beta" value={num(data?.beta) != null ? num(data.beta).toFixed(2) : '—'} />
      </div>
    </div>
  );
}
