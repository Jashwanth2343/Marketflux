/* ===================================================================
   MarketFlux UI Kit — screens.jsx
   ===================================================================
   Dashboard, StockDetail, AIScreener.
   =================================================================== */

/* -------- News card (compact) -------------------------------------- */
function NewsItem({ item, compact }) {
  return <a style={{
    display: 'flex', flexDirection: 'column', gap: 6,
    padding: compact ? '10px 0' : '12px',
    borderBottom: compact ? '1px solid var(--border)' : 'none',
    border: compact ? undefined : '1px solid var(--border)',
    background: compact ? undefined : 'var(--bg-surface)',
    cursor: 'pointer',
  }}>
    <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
      {item.tickers.map(t => (
        <Badge key={t} variant={item.sentClass}>{t}</Badge>
      ))}
      <Badge variant={item.sentClass} style={{ marginLeft: 'auto' }}>{item.sentiment}</Badge>
    </div>
    <p style={{ margin: 0, fontSize: 13, lineHeight: 1.35, color: 'var(--fg-primary)', fontWeight: 500 }}>
      {item.title}
    </p>
    <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-tertiary)' }}>
      <span>{item.source}</span><span>{item.when}</span>
    </div>
  </a>;
}

/* -------- MoversCard (Gainers/Losers tabs) ------------------------- */
function MoversCard() {
  const [tab, setTab] = useState('gainers');
  const list = window.MF_DATA[tab];
  return <Card style={{ height: '100%' }}>
    <CardHeader title="Top movers" icon="trending-up"
      right={<Badge variant="bull" dot>Markets open</Badge>} />
    <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
      {['gainers', 'losers'].map(t => {
        const active = tab === t;
        const c = t === 'gainers' ? 'var(--bull-strong)' : 'var(--bear-strong)';
        return <button key={t} onClick={() => setTab(t)} style={{
          flex: 1, padding: '10px', cursor: 'pointer',
          fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: active ? 600 : 500,
          background: 'transparent',
          color: active ? c : 'var(--fg-secondary)',
          border: 'none',
          borderBottom: active ? `2px solid ${c}` : '2px solid transparent',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
        }}>
          <Icon name={t === 'gainers' ? 'trending-up' : 'trending-down'} size={13} />
          {t === 'gainers' ? 'Gainers' : 'Losers'}
        </button>;
      })}
    </div>
    <div style={{ flex: 1, overflow: 'auto' }}>
      {list.map(s => (
        <a key={s.sym} onClick={() => window.__mfGo && window.__mfGo('stock', s.sym)} style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '9px 14px', borderBottom: '1px solid var(--border)', cursor: 'pointer',
        }}>
          <div style={{ minWidth: 0, flex: 1, paddingRight: 8 }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700, color: 'var(--fg-primary)' }}>{s.sym}</div>
            <div style={{ fontSize: 10, color: 'var(--fg-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.name}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-primary)', fontVariantNumeric: 'tabular-nums' }}>${s.px.toFixed(2)}</div>
            <Pct value={s.pct} size="s" />
          </div>
        </a>
      ))}
    </div>
  </Card>;
}

/* -------- IndexStrip --------------------------------------------- */
function IndexStrip() {
  return <Card>
    <div style={{
      display: 'flex', overflowX: 'auto', padding: '18px 20px', gap: 36,
    }}>
      {window.MF_DATA.indices.slice(0, 6).map(it => {
        const pos = it.pct >= 0;
        const cls = it.isVol ? !pos : pos;
        return <div key={it.sym} style={{ minWidth: 130, flexShrink: 0 }}>
          <Kicker>{it.name}</Kicker>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 600, fontVariantNumeric: 'tabular-nums', marginTop: 4 }}>
            {it.isVol ? '' : '$'}{typeof it.px === 'number' ? it.px.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : it.px}
          </div>
          <Pct value={it.pct} size="s" />
        </div>;
      })}
    </div>
  </Card>;
}

/* -------- AI Daily Brief — the dashboard's research brain ---------- */
function BriefItem({ item }) {
  const go = () => { if (window.__mfGo && item.go) window.__mfGo(...item.go); };
  return <div style={{
    display: 'flex', gap: 12, padding: '14px 0',
    borderBottom: '1px solid var(--border)',
  }}>
    <div style={{
      flexShrink: 0, width: 24, height: 24, borderRadius: 'var(--radius-full)',
      background: 'var(--bg-surface-2)', border: '1px solid var(--border)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
      color: 'var(--fg-secondary)', marginTop: 1,
    }}>{item.rank}</div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5, flexWrap: 'wrap' }}>
        <Badge variant={item.sentClass}>{item.tag}</Badge>
        {item.tickers.map(t => (
          <span key={t} style={{
            fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 600,
            color: 'var(--fg-secondary)', letterSpacing: '0.04em',
          }}>{t}</span>
        ))}
      </div>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)', lineHeight: 1.35, textWrap: 'pretty' }}>
        {item.headline}
      </div>
      <div style={{ fontSize: 12.5, color: 'var(--fg-secondary)', lineHeight: 1.5, marginTop: 4, textWrap: 'pretty' }}>
        {item.detail}
      </div>
      <a onClick={go} style={{
        display: 'inline-flex', alignItems: 'center', gap: 5, marginTop: 8,
        fontSize: 12, fontWeight: 600, color: 'var(--bull-strong)', cursor: 'pointer',
      }}>
        {item.action}
        <Icon name="arrow-right" size={13} />
      </a>
    </div>
  </div>;
}

function AIBriefCard() {
  const b = window.MF_DATA.brief;
  return <Card hero style={{ height: '100%' }}>
    <CardHeader title="Your brief" icon="sparkles" iconColor="var(--bull-strong)"
      right={<Badge variant="bull" dot>{b.confidence}% conf · live</Badge>} />
    <CardBody style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingTop: 14 }}>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 600,
        letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--fg-tertiary)',
      }}>{b.asOf}</div>
      <p style={{
        margin: '6px 0 4px', fontSize: 14.5, lineHeight: 1.55,
        color: 'var(--fg-primary)', textWrap: 'pretty',
        borderLeft: '2px solid var(--bull)', paddingLeft: 14,
      }}>{b.summary}</p>
      <div>
        {b.items.map(it => <BriefItem key={it.id} item={it} />)}
      </div>
      <button onClick={() => window.__mfGo && window.__mfGo('screener')} style={{
        marginTop: 12, width: '100%', padding: '11px',
        background: 'var(--bg-surface-2)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-2)', cursor: 'pointer',
        fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600, color: 'var(--fg-primary)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
      }}>
        <Icon name="message-circle" size={14} style={{ color: 'var(--bull-strong)' }} />
        Ask a follow-up about today's tape
      </button>
    </CardBody>
  </Card>;
}

/* ====================================================================
   DASHBOARD
   ==================================================================== */
function Dashboard() {
  return <div className="mf-page" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
    <IndexStrip />
    <div className="mf-bento" style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 14, minHeight: 380 }}>
      <MoversCard />
      <AIBriefCard />
    </div>
    <Card>
      <CardHeader title="Latest headlines" icon="activity" iconColor="var(--fg-secondary)"
        right={<a style={{ cursor: 'pointer', color: 'var(--bull-strong)', fontSize: 12, fontWeight: 600 }}>View all →</a>} />
      <CardBody>
        <div className="mf-news-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          {window.MF_DATA.news.map(n => <NewsItem key={n.id} item={n} />)}
        </div>
      </CardBody>
    </Card>
  </div>;
}

/* ====================================================================
   STOCK DETAIL
   ==================================================================== */
function CandleChart({ data, height = 220 }) {
  const all = data.flatMap(d => [d.h, d.l]);
  const min = Math.min(...all), max = Math.max(...all);
  const span = max - min || 1;
  const W = 720, H = height;
  const padT = 12, padB = 36; // bottom = volume
  const plotH = H - padT - padB;
  const cw = W / data.length;
  const yPx = v => padT + plotH - ((v - min) / span) * plotH;
  return <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" style={{ display: 'block' }}>
    <g stroke="rgba(255,255,255,0.04)" strokeWidth="1">
      {[0.25, 0.5, 0.75].map(f => (
        <line key={f} x1="0" y1={padT + plotH * f} x2={W} y2={padT + plotH * f} />
      ))}
    </g>
    <g fontFamily="JetBrains Mono" fontSize="9" fill="var(--fg-tertiary)">
      <text x={W - 4} y={padT + 8} textAnchor="end">{max.toFixed(0)}</text>
      <text x={W - 4} y={padT + plotH * 0.5} textAnchor="end">{((max + min) / 2).toFixed(0)}</text>
      <text x={W - 4} y={padT + plotH - 2} textAnchor="end">{min.toFixed(0)}</text>
    </g>
    {data.map((d, i) => {
      const up = d.c >= d.o;
      const color = up ? '#089981' : '#F23645';
      const x = i * cw + cw / 2;
      const bodyTop = yPx(Math.max(d.o, d.c));
      const bodyBot = yPx(Math.min(d.o, d.c));
      const bodyW = Math.max(2, cw - 4);
      return <g key={i}>
        <line x1={x} y1={yPx(d.h)} x2={x} y2={yPx(d.l)} stroke={color} strokeWidth="1" />
        <rect x={x - bodyW / 2} y={bodyTop} width={bodyW} height={Math.max(1, bodyBot - bodyTop)} fill={color} />
      </g>;
    })}
    {/* MA(20) overlay */}
    <polyline fill="none" stroke="var(--amber)" strokeWidth="1.4" strokeDasharray="3 2"
      points={data.map((d, i) => {
        const slice = data.slice(Math.max(0, i - 5), i + 1);
        const avg = slice.reduce((a, b) => a + b.c, 0) / slice.length;
        return `${i * cw + cw / 2},${yPx(avg)}`;
      }).join(' ')} />
    {/* Volume row */}
    <g>
      {data.map((d, i) => {
        const up = d.c >= d.o;
        const h = 8 + Math.abs(Math.sin(i * 0.7)) * 22;
        return <rect key={i} x={i * cw + 2} y={H - h - 4} width={cw - 4} height={h}
          fill={up ? '#089981' : '#F23645'} opacity="0.42" />;
      })}
    </g>
  </svg>;
}

function StockDetail({ sym = 'AAPL' }) {
  const ai = window.MF_DATA.ai.insights.find(i => i.sym === sym) || window.MF_DATA.ai.insights[0];
  const last = window.MF_DATA.stockHistory[window.MF_DATA.stockHistory.length - 1].c;
  const first = window.MF_DATA.stockHistory[0].c;
  const chg = last - first;
  const pct = (chg / first) * 100;
  const periods = ['1D', '5D', '1M', '3M', '6M', '1Y', '5Y', 'ALL'];
  const [period, setPeriod] = useState('1M');
  return <div className="mf-page mf-page-stock" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
    <Card hero>
      <div style={{ padding: '18px 22px', display: 'flex', alignItems: 'baseline', gap: 18, flexWrap: 'wrap' }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 32, fontWeight: 600, letterSpacing: '-0.02em' }}>{sym}</span>
        <span style={{ fontSize: 13, color: 'var(--fg-secondary)' }}>Apple Inc. · NASDAQ · USD</span>
        <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'baseline', gap: 14 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500, fontSize: 32, fontVariantNumeric: 'tabular-nums' }}>${last.toFixed(2)}</span>
          <Delta value={chg} pct={pct} size="l" />
        </span>
      </div>
      <div style={{ display: 'flex', borderTop: '1px solid var(--border)', padding: '10px 16px', gap: 4, justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 2 }}>
          {periods.map(p => (
            <button key={p} onClick={() => setPeriod(p)} style={{
              padding: '6px 11px', cursor: 'pointer',
              fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 500,
              background: period === p ? 'var(--bg-surface-2)' : 'transparent',
              color: period === p ? 'var(--fg-primary)' : 'var(--fg-secondary)',
              border: 'none',
              borderRadius: 6,
            }}>{p}</button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <Button variant="secondary" icon="briefcase">Add to portfolio</Button>
          <Button variant="primary" icon="sparkles">AI brief</Button>
        </div>
      </div>
      <CardBody style={{ padding: 0 }}>
        <CandleChart data={window.MF_DATA.stockHistory} />
      </CardBody>
    </Card>

    <div className="mf-split-2" style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14 }}>
      <Card>
        <CardHeader title="Fundamentals" icon="bar-chart-2" />
        <CardBody className="mf-fund-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          {[
            ['MARKET CAP', '$3.02T'],
            ['P/E (FWD)', '28.2'],
            ['EPS (TTM)', '$6.82'],
            ['REVENUE TTM', '$391B'],
            ['DIVIDEND', '0.51%'],
            ['52W HIGH', '$199.62'],
            ['52W LOW', '$164.08'],
            ['BETA', '1.24'],
          ].map(([k, v]) => (
            <div key={k}>
              <Kicker>{k}</Kicker>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 600, marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>{v}</div>
            </div>
          ))}
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="AI thesis" icon="sparkles" iconColor="var(--bull-strong)"
          right={<Badge variant="bull">{ai.conf}% confidence</Badge>} />
        <CardBody>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8 }}>
            <Badge variant={ai.view === 'BULLISH' ? 'bull' : ai.view === 'BEARISH' ? 'bear' : 'warn'}>{ai.view}</Badge>
            <span style={{ fontSize: 12, color: 'var(--fg-secondary)' }}>{ai.horizon} target</span>
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 28, fontWeight: 500, color: 'var(--bull-strong)', fontVariantNumeric: 'tabular-nums' }}>${ai.target}</div>
          <div style={{ fontSize: 13, color: 'var(--fg-primary)', lineHeight: 1.55, marginTop: 10, borderLeft: '2px solid var(--bull)', paddingLeft: 12 }}>
            {ai.thesis}
          </div>
        </CardBody>
      </Card>
    </div>
  </div>;
}

/* ====================================================================
   AI SCREENER
   ==================================================================== */
function AIScreener() {
  const [query, setQuery] = useState('Mega-cap tech stocks with PE under 30 and bullish AI sentiment');
  const [filters, setFilters] = useState(['Technology', 'Mega-cap', 'PE < 30', 'AI: BULLISH']);
  const results = window.MF_DATA.screenerResults;

  return <div className="mf-page" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
    <Card hero>
    <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 22, letterSpacing: '-0.015em' }}>AI screener</div>
        <div style={{ fontSize: 13, color: 'var(--fg-secondary)', marginTop: 2 }}>Ask in plain English. FluxAI translates to filters.</div>
      </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          background: 'var(--bg-surface-2)', border: '1px solid var(--bull-border)',
          padding: '10px 14px', borderRadius: 8,
        }}>
          <Icon name="sparkles" size={16} style={{ color: 'var(--bull-strong)' }} />
          <input value={query} onChange={e => setQuery(e.target.value)}
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none',
              fontFamily: 'var(--font-body)', fontSize: 14, color: 'var(--fg-primary)' }} />
          <Button variant="primary" icon="search">Run screener</Button>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {filters.map(f => (
            <span key={f} style={{
              fontFamily: 'var(--font-body)', fontSize: 12,
              padding: '5px 10px',
              color: 'var(--bull-strong)', background: 'var(--bull-bg)',
              border: '1px solid var(--bull-border)', borderRadius: 9999,
              display: 'inline-flex', alignItems: 'center', gap: 8,
            }}>
              {f}
              <a onClick={() => setFilters(filters.filter(x => x !== f))} style={{ cursor: 'pointer', color: 'var(--fg-tertiary)' }}>×</a>
            </span>
          ))}
        </div>
      </div>
    </Card>

    <Card>
      <CardHeader title={`${results.length} matches`} icon="list-filter"
        right={<Button variant="secondary" icon="download">Export CSV</Button>} />
      <div style={{ overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-body)', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Ticker', 'Name', 'Market Cap', 'P/E', 'Last', 'Δ %', 'Sector', ''].map(h => (
                <th key={h} style={{
                  textAlign: 'left', padding: '8px 14px',
                  fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                  letterSpacing: '0.14em', color: 'var(--fg-secondary)', textTransform: 'uppercase',
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((r, i) => (
              <tr key={r.sym} style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
                onClick={() => window.__mfGo && window.__mfGo('stock', r.sym)}>
                <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--bull-strong)' }}>{r.sym}</td>
                <td style={{ padding: '10px 14px', color: 'var(--fg-primary)' }}>{r.name}</td>
                <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>${r.mcap}</td>
                <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>{r.pe}</td>
                <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>${r.px.toFixed(2)}</td>
                <td style={{ padding: '10px 14px' }}><Pct value={r.pct} size="s" /></td>
                <td style={{ padding: '10px 14px', color: 'var(--fg-secondary)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{r.sector}</td>
                <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                  <Icon name="chevron-right" size={14} style={{ color: 'var(--fg-tertiary)' }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  </div>;
}

Object.assign(window, {
  Dashboard, StockDetail, AIScreener,
  AIBriefCard, NewsItem, MoversCard, IndexStrip, CandleChart,
});
