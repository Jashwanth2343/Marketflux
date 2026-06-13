import { useEffect, useState } from 'react';
import { FileText, GitCompareArrows, Search, Loader2, Plus, Minus } from 'lucide-react';

import { Card } from '@/components/ui/card';
import api from '@/lib/api';

const TABS = [
  { key: 'recent', label: 'Recent filings', icon: FileText },
  { key: 'diff', label: 'Risk factor Δ', icon: GitCompareArrows },
  { key: 'search', label: 'Search inside', icon: Search },
];

const FORM_BADGE = {
  '10-K': 'text-primary border-primary/20 bg-primary/10',
  '10-Q': 'text-sky-400 border-sky-400/35 bg-sky-400/10',
  '8-K': 'text-violet-400 border-violet-400/35 bg-violet-400/10',
};

// 8-K item codes worth glossing for the reader.
const ITEM_HINTS = {
  '2.02': 'earnings', '5.02': 'exec change', '1.01': 'material agreement',
  '7.01': 'reg FD', '8.01': 'other event', '5.07': 'shareholder vote',
};

function FormBadge({ form }) {
  return (
    <span className={`inline-flex px-1.5 py-0.5 rounded border font-mono text-[10px] ${FORM_BADGE[form] || FORM_BADGE['8-K']}`}>
      {form}
    </span>
  );
}

function itemsHint(items) {
  if (!items) return '';
  const hints = items.split(',').map((c) => ITEM_HINTS[c.trim()]).filter(Boolean);
  return hints.length ? ` · ${hints.join(', ')}` : '';
}

function RecentTab({ ticker }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    setRows(null); setError('');
    api.get(`/filings/${ticker}`)
      .then((res) => { if (alive) setRows(res?.data?.filings || []); })
      .catch((err) => { if (alive) setError(err?.response?.data?.detail || 'No EDGAR filings found.'); });
    return () => { alive = false; };
  }, [ticker]);

  if (error) return <div className="px-4 py-8 text-center text-xs text-muted-foreground">{error}</div>;
  if (!rows) return <div className="px-4 py-8 text-center text-xs text-muted-foreground"><Loader2 className="inline w-3 h-3 animate-spin mr-1.5" />Reading EDGAR…</div>;
  return (
    <div>
      <div className="grid grid-cols-12 px-4 py-2 border-b border-border bg-muted/40 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
        <div className="col-span-2">form</div>
        <div className="col-span-3">filed</div>
        <div className="col-span-3">period</div>
        <div className="col-span-4">notes</div>
      </div>
      {rows.map((f) => (
        <div key={f.accession} className="grid grid-cols-12 items-center px-4 py-2 border-b border-border last:border-0 text-xs hover:bg-card/60">
          <div className="col-span-2"><FormBadge form={f.form} /></div>
          <div className="col-span-3 font-mono tabular-nums text-muted-foreground">{f.filed}</div>
          <div className="col-span-3 font-mono tabular-nums text-muted-foreground">{f.report_date || '—'}</div>
          <div className="col-span-4 font-mono text-[11px] text-muted-foreground truncate">
            {f.items ? `items ${f.items}${itemsHint(f.items)}` : f.primary_doc}
          </div>
        </div>
      ))}
    </div>
  );
}

function DiffTab({ ticker }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const run = () => {
    setLoading(true); setError(''); setData(null);
    api.get(`/filings/${ticker}/risk-diff`)
      .then((res) => setData(res?.data))
      .catch((err) => setError(err?.response?.data?.detail || 'Diff unavailable for this name.'))
      .finally(() => setLoading(false));
  };

  if (!data && !loading && !error) {
    return (
      <div className="px-4 py-8 text-center">
        <button onClick={run}
          className="rounded-lg border border-primary/20 bg-primary/10 px-4 py-2 font-mono text-xs text-primary hover:bg-primary/15">
          Diff the two latest 10-K Risk Factors
        </button>
        <p className="mt-2 text-[10px] text-muted-foreground">Downloads both filings from EDGAR — first run takes ~15s, then cached.</p>
      </div>
    );
  }
  if (loading) return <div className="px-4 py-10 text-center text-xs text-muted-foreground"><Loader2 className="inline w-3 h-3 animate-spin mr-1.5" />Pulling both 10-Ks and diffing Item 1A…</div>;
  if (error) return <div className="px-4 py-8 text-center text-xs text-muted-foreground">{error}</div>;

  return (
    <div className="p-4 space-y-3 text-xs">
      <div className="flex flex-wrap items-center gap-3 font-mono text-[11px]">
        <span className="text-muted-foreground">{data.old_filing?.filed} → {data.new_filing?.filed}</span>
        <span className="text-muted-foreground">similarity <span className="text-foreground">{data.similarity_pct}%</span></span>
        <span className="text-green-500">+{data.added_count} added</span>
        <span className="text-red-500">−{data.removed_count} removed</span>
      </div>
      <div className="font-mono text-[11px] text-primary">{data.read}</div>
      {(data.added || []).length > 0 && (
        <div className="space-y-1.5">
          <div className="font-mono text-[10px] uppercase tracking-wider text-green-500">New risk language</div>
          {data.added.map((p, i) => (
            <div key={i} className="flex gap-2 rounded border border-green-500/20 bg-green-500/[0.04] p-2">
              <Plus className="w-3 h-3 mt-0.5 shrink-0 text-green-500" />
              <p className="text-muted-foreground leading-relaxed">{p}</p>
            </div>
          ))}
        </div>
      )}
      {(data.removed || []).length > 0 && (
        <div className="space-y-1.5">
          <div className="font-mono text-[10px] uppercase tracking-wider text-red-500">Dropped risk language</div>
          {data.removed.map((p, i) => (
            <div key={i} className="flex gap-2 rounded border border-red-500/20 bg-red-500/[0.04] p-2">
              <Minus className="w-3 h-3 mt-0.5 shrink-0 text-red-500" />
              <p className="text-muted-foreground leading-relaxed">{p}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SearchTab({ ticker }) {
  const [q, setQ] = useState('');
  const [form, setForm] = useState('10-K');
  const [passages, setPassages] = useState(null);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const run = (e) => {
    e?.preventDefault();
    if (q.trim().length < 2) return;
    setLoading(true); setError(''); setPassages(null);
    api.get(`/filings/${ticker}/search`, { params: { q: q.trim(), form } })
      .then((res) => { setPassages(res?.data?.passages || []); setMeta(res?.data); })
      .catch((err) => setError(err?.response?.data?.detail || 'Search unavailable.'))
      .finally(() => setLoading(false));
  };

  return (
    <div className="p-4 space-y-3">
      <form onSubmit={run} className="flex items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={`Ask the ${form} — e.g. "customer concentration", "China exposure", "litigation"`}
          className="flex-1 rounded border border-border bg-card px-3 py-1.5 text-xs font-mono focus:border-primary/60 focus:outline-none"
          data-testid="filings-search-input"
        />
        <select value={form} onChange={(e) => setForm(e.target.value)}
          className="rounded border border-border bg-card px-2 py-1.5 font-mono text-xs">
          <option value="10-K">10-K</option>
          <option value="10-Q">10-Q</option>
        </select>
        <button type="submit" disabled={loading || q.trim().length < 2}
          className="rounded border border-primary/20 bg-primary/10 px-3 py-1.5 font-mono text-xs text-primary hover:bg-primary/15 disabled:opacity-40">
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Search'}
        </button>
      </form>
      {error && <div className="text-xs text-muted-foreground">{error}</div>}
      {loading && <div className="text-xs text-muted-foreground"><Loader2 className="inline w-3 h-3 animate-spin mr-1.5" />Reading the {form} full text…</div>}
      {passages && !loading && (
        <div className="space-y-2">
          {meta?.filed && (
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              {meta.form} filed {meta.filed} · {meta.total_chunks} chunks scanned
            </div>
          )}
          {passages.length === 0 ? (
            <div className="text-xs text-muted-foreground">No relevant passages — try different words.</div>
          ) : passages.map((p, i) => (
            <div key={i} className="rounded border border-border bg-card/60 p-2.5">
              <p className="text-xs text-muted-foreground leading-relaxed">{p.text}</p>
              {p.relevance != null && (
                <div className="mt-1 font-mono text-[10px] text-primary">relevance {p.relevance}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function FilingsPanel({ ticker }) {
  const [tab, setTab] = useState('recent');
  if (!ticker) return null;
  return (
    <Card className="overflow-hidden" data-testid="filings-panel">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-primary" />
          <span className="text-sm font-semibold">SEC Filings</span>
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">EDGAR full text</span>
        </div>
        <div className="flex items-center gap-1">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button key={key} onClick={() => setTab(key)}
              className={`flex items-center gap-1 rounded px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider transition-colors ${
                tab === key
                  ? 'bg-primary/15 text-primary border border-primary/20'
                  : 'text-muted-foreground hover:text-foreground border border-transparent'
              }`}>
              <Icon className="w-3 h-3" /> {label}
            </button>
          ))}
        </div>
      </div>
      {tab === 'recent' && <RecentTab ticker={ticker} />}
      {tab === 'diff' && <DiffTab ticker={ticker} />}
      {tab === 'search' && <SearchTab ticker={ticker} />}
    </Card>
  );
}
