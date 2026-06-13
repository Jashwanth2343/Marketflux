import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, Loader2, TrendingUp, TrendingDown, X, ArrowRight, AlertTriangle } from 'lucide-react';
import api from '@/lib/api';
import { cn } from '@/lib/utils';

/* Inline, grounded AI tape-read for a single security — the terminal's answer
   region. Reuses GET /intelligence/explain/{ticker}: { price, change_percent,
   explanation, sources[] }. Self-fetching + abortable; renders the AI text as
   plain text (never HTML) and only allows http(s) source links. */

const TICKER_RE = /^[A-Z][A-Z.\-^]{0,5}$/;
const safeHref = (url) => (typeof url === 'string' && /^https?:\/\//i.test(url) ? url : null);

export default function ReadPanel({ ticker, onClose }) {
  const [state, setState] = useState({ status: 'idle' });
  const navigate = useNavigate();
  const abortRef = useRef(null);

  useEffect(() => {
    if (!ticker) return;
    const t = String(ticker).toUpperCase();
    if (!TICKER_RE.test(t)) {
      setState({ status: 'error', error: `“${ticker}” doesn’t look like a ticker.` });
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setState({ status: 'loading' });
    api.get(`/intelligence/explain/${encodeURIComponent(t)}`, { signal: controller.signal })
      .then(({ data }) => setState({ status: 'done', data }))
      .catch((err) => {
        if (controller.signal.aborted) return;
        setState({ status: 'error', error: err?.response?.data?.detail || 'Could not generate a read for this ticker.' });
      });
    return () => controller.abort();
  }, [ticker]);

  if (!ticker) return null;
  const t = String(ticker).toUpperCase();
  const { status, data, error } = state;
  const sources = Array.isArray(data?.sources) ? data.sources : [];

  return (
    <div className="border border-border bg-card rounded-lg p-4" data-testid="read-panel" aria-live="polite">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 font-mono">
          <Zap className="w-4 h-4 text-primary" />
          <span className="font-bold text-foreground">{t}</span>
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground/70">AI tape read</span>
          {status === 'done' && data?.price != null && (
            <span className="text-sm text-foreground">${Number(data.price).toFixed(2)}</span>
          )}
          {status === 'done' && data?.change_percent != null && (
            <span className={cn('flex items-center gap-1 text-xs', Number(data.change_percent) >= 0 ? 'text-gain' : 'text-loss')}>
              {Number(data.change_percent) >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              {Number(data.change_percent) >= 0 ? '+' : ''}{data.change_percent}%
            </span>
          )}
        </div>
        <button onClick={onClose} className="p-1 rounded text-muted-foreground/60 hover:text-loss hover:bg-loss/10 transition-colors" aria-label="Dismiss read">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="mt-3">
        {status === 'loading' && (
          <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" /> Reading {t}’s tape…
          </div>
        )}
        {status === 'error' && (
          <p className="flex items-center gap-2 text-xs font-mono text-loss">
            <AlertTriangle className="w-3.5 h-3.5" /> {error}
          </p>
        )}
        {status === 'done' && (
          <div className="space-y-3">
            <p className="text-sm leading-relaxed text-foreground whitespace-pre-line">{data?.explanation || 'No read available.'}</p>
            {sources.length > 0 && (
              <div className="space-y-1 border-t border-border pt-2">
                <span className="text-[10px] uppercase tracking-widest text-muted-foreground/70 font-mono">Sources</span>
                {sources.map((s, i) => {
                  const href = safeHref(s?.url);
                  const label = `${s?.title || 'source'}${s?.source ? ` — ${s.source}` : ''}`;
                  return href ? (
                    <a key={i} href={href} target="_blank" rel="noreferrer noopener"
                      className="block truncate text-[11px] text-muted-foreground hover:text-primary transition-colors">↳ {label}</a>
                  ) : (
                    <span key={i} className="block truncate text-[11px] text-muted-foreground/70">↳ {label}</span>
                  );
                })}
              </div>
            )}
            <button
              onClick={() => { sessionStorage.setItem('copilot_ask', `Dig deeper on ${t}: ${data?.explanation || ''}`.trim()); navigate('/copilot'); }}
              className="flex items-center gap-1 text-[11px] font-mono text-primary hover:underline"
            >
              Dig deeper in Copilot <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
