/* MarketFlux · Autonomous Core · canvas
   Infinite dot-grid canvas with floating agent artifact cards
   connected by curved data-flow edges. */

// Babel script blocks are isolated scopes — rebind React hooks here.
const { useState, useEffect, useRef, useMemo } = React;

/* ================================================================
   ARTIFACT POSITIONS — virtual canvas coords. Cards are designed
   to fit on a ~1820×940 visible area (with left rail open).
   ================================================================ */
const CARD_LAYOUT = {
  brief:     { x:  20, y:  20, w: 320, h: 460 },
  sectors:   { x: 360, y:  20, w: 360, h: 220 },
  candidates:{ x: 360, y: 260, w: 360, h: 308 },
  backtest:  { x: 360, y: 588, w: 360, h: 250 },
  live:      { x: 740, y:  20, w: 420, h: 480 },
  orders:    { x: 740, y: 520, w: 420, h: 318 },
  risk:      { x:1180, y:  20, w: 300, h: 280 },
  watchers:  { x:1180, y: 320, w: 300, h: 220 },
  hedge:     { x:1180, y: 560, w: 300, h: 278 },
};

/* Edges between cards (curved SVG). live status = animated */
const EDGES = [
  { from: 'brief',      to: 'sectors',    side: 'right-left', live: false },
  { from: 'sectors',    to: 'candidates', side: 'bottom-top', live: false },
  { from: 'candidates', to: 'backtest',   side: 'bottom-top', live: false },
  { from: 'candidates', to: 'live',       side: 'right-left', live: true  },
  { from: 'backtest',   to: 'live',       side: 'right-left', live: true  },
  { from: 'live',       to: 'orders',     side: 'bottom-top', live: true  },
  { from: 'live',       to: 'risk',       side: 'right-left', live: false },
  { from: 'orders',     to: 'hedge',      side: 'right-left', live: false },
];

/* ================================================================
   CARD CHROME
   ================================================================ */
function ArtifactCard({ id, layout, live, children, kicker, title, icon, badge }) {
  const L = layout[id];
  return <article id={'card-' + id} className={'artifact' + (live ? ' artifact-live' : '')}
    data-screen-label={id} style={{
      left: L.x, top: L.y, width: L.w, height: L.h,
    }}>
    <header className="artifact-head">
      <span style={{
        width: 22, height: 22, borderRadius: 6,
        background: live ? 'var(--agent-grad)' : 'rgba(244,239,227,0.04)',
        border: '1px solid ' + (live ? 'transparent' : 'var(--hairline)'),
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        color: live ? '#0A1006' : 'var(--fg-secondary)',
      }}>
        <Icon name={icon} size={11} stroke={live ? 2.4 : 1.75} />
      </span>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0, minWidth: 0, flex: 1 }}>
        <span className="micro" style={{ fontSize: 9.5, color: 'var(--fg-tertiary)' }}>{kicker}</span>
        <span style={{ fontSize: 12.5, color: 'var(--fg-primary)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</span>
      </div>
      {badge}
      <button className="btn-icon" style={{ width: 22, height: 22, border: 0 }} aria-label="More">
        <Icon name="more-horizontal" size={12} />
      </button>
    </header>
    {children}
  </article>;
}

/* ================================================================
   1 · STRATEGY BRIEF — editorial document card
   ================================================================ */
function BriefCard({ layout }) {
  return <ArtifactCard id="brief" layout={layout}
    kicker="STRATEGY BRIEF · 11:42 AM"
    title="Momentum Hunter v3"
    icon="book-open-text"
    badge={<span className="micro" style={{ fontSize: 9, color: 'var(--fg-tertiary)', padding: '2px 6px', borderRadius: 4, border: '1px solid var(--hairline)' }}>DOC</span>}>
    <div className="artifact-body" style={{ overflow: 'hidden', position: 'relative' }}>
      <div style={{
        fontFamily: 'var(--serif)', fontSize: 22, lineHeight: 1.18,
        color: 'var(--fg-primary)', letterSpacing: '-0.01em', marginBottom: 12,
      }}>
        Trade the breadth, not the index.
      </div>
      <div style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--fg-secondary)', marginBottom: 14 }}>
        Hunt top-decile relative-strength large caps as breadth tightens. Size on 21-day ATR, exit on 20-EMA loss. Optimised for 5–21 day horizons.
      </div>

      <div className="micro" style={{ marginBottom: 8 }}>RULES</div>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 7 }}>
        {[
          { kw: 'Universe', t: 'S&P 500 ex-utilities · float > $5B' },
          { kw: 'Entry',    t: 'RS rank ≥ 90 · MACD bull cross · vol > 1.2× avg' },
          { kw: 'Sizing',   t: '0.8% portfolio risk · ATR(14) stop' },
          { kw: 'Exit',     t: 'Close < 20-EMA OR +5.6% target hit' },
        ].map((r, i) => (
          <li key={i} style={{ display: 'flex', gap: 10, fontSize: 12, color: 'var(--fg-secondary)', lineHeight: 1.45 }}>
            <span style={{ minWidth: 60, color: 'var(--fg-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 10.5, letterSpacing: '0.08em', textTransform: 'uppercase', paddingTop: 2 }}>{r.kw}</span>
            <span>{r.t}</span>
          </li>
        ))}
      </ul>

      <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--hairline-soft)', display: 'flex', justifyContent: 'space-between' }}>
        <Stat label="HORIZON" v="5–21d" />
        <Stat label="MAX RISK" v="0.8%" />
        <Stat label="SHARPE" v="1.84" tone="#4ADE80" />
        <Stat label="WIN" v="62%" tone="#4ADE80" />
      </div>
    </div>
  </ArtifactCard>;
}

function Stat({ label, v, tone }) {
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
    <span className="micro" style={{ fontSize: 9, color: 'var(--fg-tertiary)' }}>{label}</span>
    <span className="mono" style={{ fontSize: 12.5, color: tone || 'var(--fg-primary)', fontWeight: 500 }}>{v}</span>
  </div>;
}

/* ================================================================
   2 · UNIVERSE SCAN — sector heatmap
   ================================================================ */
const SECTORS = [
  { n: 'TECH',  v: +2.84, hot: 3 },
  { n: 'COMM',  v: +1.92, hot: 2 },
  { n: 'DISC',  v: +1.15, hot: 2 },
  { n: 'FIN',   v: +0.78, hot: 1 },
  { n: 'HC',    v: +0.42, hot: 1 },
  { n: 'IND',   v: -0.18, hot: 0 },
  { n: 'STAPL', v: -0.31, hot: 0 },
  { n: 'MAT',   v: -0.68, hot: -1 },
  { n: 'EN',    v: -1.24, hot: -1 },
  { n: 'RE',    v: -1.86, hot: -2 },
  { n: 'UTIL',  v: -2.04, hot: -2 },
];
function toneFor(v) {
  if (v >= 2) return 'rgba(34,197,94,0.55)';
  if (v >= 1) return 'rgba(34,197,94,0.36)';
  if (v >= 0) return 'rgba(34,197,94,0.18)';
  if (v >= -1) return 'rgba(239,68,68,0.22)';
  if (v >= -2) return 'rgba(239,68,68,0.4)';
  return 'rgba(239,68,68,0.55)';
}

function SectorsCard({ layout }) {
  return <ArtifactCard id="sectors" layout={layout}
    kicker="UNIVERSE SCAN · 5D"
    title="Sector momentum"
    icon="grid-2x2"
    badge={<span className="mono" style={{ fontSize: 10, color: 'var(--fg-secondary)' }}>11 sectors</span>}>
    <div className="artifact-body">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 5, marginBottom: 10 }}>
        {SECTORS.map((s, i) => (
          <div key={s.n} className="heat-cell slide-up" style={{
            background: toneFor(s.v), padding: '6px 4px', textAlign: 'center',
            animationDelay: i * 25 + 'ms',
            border: '1px solid ' + (s.v > 0 ? 'rgba(74,222,128,0.35)' : 'rgba(239,68,68,0.32)'),
          }}>
            <div className="mono" style={{ fontSize: 9.5, color: 'var(--fg-primary)', letterSpacing: '0.05em' }}>{s.n}</div>
            <div className="mono" style={{ fontSize: 11, fontWeight: 600, color: s.v >= 0 ? '#4ADE80' : '#F87171', marginTop: 1 }}>
              {s.v >= 0 ? '+' : '−'}{Math.abs(s.v).toFixed(2)}
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--fg-tertiary)' }}>
        <span>Tech leads · breadth 68%</span>
        <span className="mono">+0.84% net</span>
      </div>
    </div>
  </ArtifactCard>;
}

/* ================================================================
   3 · TOP CANDIDATES — ranked ticker list with factor bars
   ================================================================ */
const CANDIDATES = [
  { sym: 'NVDA', name: 'NVIDIA',         px: 178.40, ch: +4.21, score: 94, factors: [9,8,9,7] },
  { sym: 'AVGO', name: 'Broadcom',       px: 1842.10, ch: +3.14, score: 88, factors: [8,9,7,8] },
  { sym: 'CRWD', name: 'CrowdStrike',    px: 392.55, ch: +2.78, score: 84, factors: [9,7,8,7] },
  { sym: 'AMD',  name: 'Adv Micro Dev',  px: 448.81, ch: +2.04, score: 79, factors: [7,8,8,6] },
  { sym: 'NFLX', name: 'Netflix',        px: 1124.30, ch: +1.86, score: 76, factors: [7,7,7,8] },
  { sym: 'META', name: 'Meta Platforms', px: 712.80, ch: +1.42, score: 72, factors: [6,7,7,7] },
];

function CandidatesCard({ layout }) {
  return <ArtifactCard id="candidates" layout={layout}
    kicker="RANKED CANDIDATES · TOP 6"
    title="High-conviction list"
    icon="list-ordered"
    badge={<span className="mono" style={{ fontSize: 10, color: '#4ADE80' }}>passing 412 → 6</span>}>
    <div className="artifact-body" style={{ paddingTop: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 9.5, color: 'var(--fg-tertiary)', letterSpacing: '0.1em', padding: '4px 0 8px', borderBottom: '1px solid var(--hairline-soft)' }}>
        <span>#</span>
        <span style={{ flex: 1, paddingLeft: 8 }}>TICKER</span>
        <span style={{ width: 70, textAlign: 'right' }}>5D</span>
        <span style={{ width: 70, textAlign: 'right' }}>SCORE</span>
      </div>
      {CANDIDATES.map((c, i) => (
        <div key={c.sym} className="slide-up" style={{
          display: 'flex', alignItems: 'center', padding: '7px 0',
          borderBottom: i === CANDIDATES.length - 1 ? 0 : '1px solid var(--hairline-soft)',
          animationDelay: i * 40 + 'ms',
        }}>
          <span className="mono" style={{ fontSize: 10, color: 'var(--fg-quaternary)', width: 18 }}>{String(i+1).padStart(2,'0')}</span>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 0, paddingLeft: 8, minWidth: 0 }}>
            <span className="mono" style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-primary)', letterSpacing: '0.03em' }}>{c.sym}</span>
            <span style={{ fontSize: 10, color: 'var(--fg-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.name}</span>
          </div>
          <span className="mono" style={{ width: 70, textAlign: 'right', fontSize: 11.5, color: '#4ADE80' }}>+{c.ch.toFixed(2)}%</span>
          <div style={{ width: 70, display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'flex-end' }}>
            <div style={{ flex: 1, height: 4, background: 'rgba(244,239,227,0.06)', borderRadius: 99, overflow: 'hidden' }}>
              <div style={{ width: c.score + '%', height: '100%', background: 'var(--agent-grad)' }} />
            </div>
            <span className="mono" style={{ fontSize: 11, color: 'var(--fg-primary)', minWidth: 22, textAlign: 'right' }}>{c.score}</span>
          </div>
        </div>
      ))}
    </div>
  </ArtifactCard>;
}

/* ================================================================
   4 · BACKTEST EQUITY CURVE
   ================================================================ */
function BacktestCard({ layout }) {
  // Equity curve: strategy vs SPY (90 days)
  const N = 60;
  const strat = [];
  const bench = [];
  let s = 100, b = 100;
  let rng = 9;
  const r = () => { rng = (rng * 9301 + 49297) % 233280; return rng / 233280; };
  for (let i = 0; i < N; i++) {
    s += (r() - 0.42) * 0.85;
    b += (r() - 0.48) * 0.55;
    strat.push(s);
    bench.push(b);
  }
  const w = 320, h = 130;
  const allV = [...strat, ...bench];
  const min = Math.min(...allV) * 0.99;
  const max = Math.max(...allV) * 1.01;
  const x = (i) => (i / (N-1)) * w;
  const y = (v) => h - ((v - min) / (max - min)) * h;
  const stratPath = strat.map((v, i) => (i === 0 ? 'M' : 'L') + x(i).toFixed(1) + ',' + y(v).toFixed(1)).join(' ');
  const benchPath = bench.map((v, i) => (i === 0 ? 'M' : 'L') + x(i).toFixed(1) + ',' + y(v).toFixed(1)).join(' ');
  const stratArea = stratPath + ' L' + w + ',' + h + ' L0,' + h + ' Z';
  const finalS = strat[N-1], finalB = bench[N-1];

  return <ArtifactCard id="backtest" layout={layout}
    kicker="BACKTEST · 90D"
    title="Strategy vs SPY"
    icon="line-chart"
    badge={<span className="mono" style={{ fontSize: 10, color: '#4ADE80' }}>+{(finalS - 100).toFixed(1)}%</span>}>
    <div className="artifact-body" style={{ paddingTop: 4 }}>
      <div style={{ display: 'flex', gap: 16, marginBottom: 8, fontSize: 11 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 8, height: 8, borderRadius: 99, background: '#4ADE80' }} /> Strategy
          <span className="mono" style={{ color: '#4ADE80', marginLeft: 4 }}>+{(finalS - 100).toFixed(2)}%</span>
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--fg-tertiary)' }}>
          <span style={{ width: 8, height: 1.5, background: 'var(--fg-tertiary)' }} /> SPY
          <span className="mono" style={{ marginLeft: 4 }}>+{(finalB - 100).toFixed(2)}%</span>
        </span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: '100%', height: 130, display: 'block' }}>
        <defs>
          <linearGradient id="stratFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4ADE80" stopOpacity="0.32" />
            <stop offset="100%" stopColor="#4ADE80" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map(f => (
          <line key={f} x1="0" x2={w} y1={f*h} y2={f*h} stroke="rgba(244,239,227,0.04)" strokeWidth="1" />
        ))}
        <path d={stratArea} fill="url(#stratFill)" className="draw" />
        <path d={benchPath} fill="none" stroke="rgba(168,160,145,0.5)" strokeWidth="1.2" strokeDasharray="3 3" className="draw" />
        <path d={stratPath} fill="none" stroke="#4ADE80" strokeWidth="1.8" strokeLinecap="round" className="draw" />
        <circle cx={x(N-1)} cy={y(finalS)} r="3" fill="#4ADE80">
          <animate attributeName="r" values="3;5;3" dur="2s" repeatCount="indefinite" />
        </circle>
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--hairline-soft)' }}>
        <Stat label="SHARPE" v="1.84" tone="#4ADE80" />
        <Stat label="MAX DD" v="−4.2%" tone="#F87171" />
        <Stat label="TRADES" v="38" />
        <Stat label="HIT" v="62%" tone="#4ADE80" />
      </div>
    </div>
  </ArtifactCard>;
}

/* ================================================================
   5 · LIVE REASONING — streaming agent log (THE FOCAL CARD)
   ================================================================ */
const PHASES = [
  { id: 'intent',   label: 'Intent',    icon: 'message-square' },
  { id: 'context',  label: 'Context',   icon: 'database' },
  { id: 'research', label: 'Research',  icon: 'search' },
  { id: 'reason',   label: 'Reason',    icon: 'brain' },
  { id: 'compose',  label: 'Compose',   icon: 'check-circle-2' },
];

const SCRIPT = [
  { ms:   0, ph: 0, k: 'sys',  t: '$ flux.run --agent=momentum --mode=paper' },
  { ms: 140, ph: 0, k: 'task', t: 'parse_intent()', s: 'horizon=5-21d · cap=$5,000 · risk=med' },
  { ms: 320, ph: 0, k: 'ok',   t: 'intent ✓ 142ms' },
  { ms: 480, ph: 1, k: 'tool', t: 'alpaca.account.read()', s: 'cash $90,520 · bp $181k' },
  { ms: 720, ph: 1, k: 'ok',   t: 'context ✓ 78ms' },
  { ms: 880, ph: 2, k: 'tool', t: 'screener.run("rs>=90, vol>1.2x, mcap>5B")', s: '412 → 22 → 6 candidates' },
  { ms:1120, ph: 2, k: 'tool', t: 'indicators.compute(["RSI","MACD","EMA20","ATR"])', s: '6 tickers · 4 signals' },
  { ms:1380, ph: 2, k: 'tool', t: 'news.scan(top_6, 24h)', s: '34 items · sentiment +0.48' },
  { ms:1660, ph: 2, k: 'tool', t: 'peers.compare(NVDA, ["AVGO","AMD","INTC","MRVL"])', s: 'RS rank 1/5' },
  { ms:1900, ph: 2, k: 'ok',   t: 'research ✓ 1.32s · 18 signals fused' },
  { ms:2120, ph: 3, k: 'task', t: 'agent.reason()', s: 'thesis: tech leadership + earnings tailwind' },
  { ms:2360, ph: 3, k: 'tool', t: 'sizer.kelly_atr(0.8%)', s: 'qty=28 · stop -3.8% · target +5.6%' },
  { ms:2620, ph: 3, k: 'ok',   t: 'sizing ✓ 78ms' },
  { ms:2820, ph: 4, k: 'task', t: 'compose_orders()', s: '3 orders · paper account · pending review' },
  { ms:3100, ph: 4, k: 'note', t: '“NVDA reclaimed 20-EMA on 1.6× avg volume with constructive options skew. Top of momentum cohort vs SPX.”' },
  { ms:3420, ph: 4, k: 'ok',   t: 'ready for review · awaiting approval' },
];

function LiveCard({ layout }) {
  const [events, setEvents] = useState([]);
  const [phase, setPhase] = useState(0);
  const [done, setDone] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    const timers = [];
    SCRIPT.forEach(ev => {
      timers.push(setTimeout(() => {
        setEvents(p => [...p, ev]);
        setPhase(p => Math.max(p, ev.ph));
      }, ev.ms));
    });
    timers.push(setTimeout(() => setDone(true), SCRIPT[SCRIPT.length - 1].ms + 600));
    return () => timers.forEach(clearTimeout);
  }, []);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [events.length]);

  const kindColor = (k) => ({
    sys: 'var(--fg-quaternary)', task: 'var(--fg-primary)',
    tool: '#4ADE80', ok: '#4ADE80', note: '#F5C147',
  }[k] || 'var(--fg-secondary)');

  return <ArtifactCard id="live" layout={layout} live
    kicker={done ? 'COMPLETE · 3.42s · 14 TOOLS' : 'AGENT REASONING · LIVE'}
    title="Momentum Hunter · run #2843"
    icon="zap"
    badge={
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
        {!done && <span className="pulse-dot" />}
        <span className="mono" style={{ fontSize: 10, color: done ? '#4ADE80' : 'var(--fg-secondary)', letterSpacing: '0.08em' }}>
          {done ? 'READY' : 'STREAMING'}
        </span>
      </span>
    }>
    {/* Phase pipeline */}
    <div style={{
      padding: '12px 14px', borderBottom: '1px solid var(--hairline-soft)',
      display: 'flex', alignItems: 'center', gap: 0,
    }}>
      {PHASES.map((p, i) => {
        const active = phase >= i;
        const current = phase === i && !done;
        return <React.Fragment key={p.id}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, minWidth: 56 }}>
            <span style={{
              width: 24, height: 24, borderRadius: 7,
              background: active ? (current ? 'var(--agent-grad)' : 'rgba(74,222,128,0.15)') : 'rgba(244,239,227,0.04)',
              border: '1px solid ' + (active ? 'rgba(74,222,128,0.4)' : 'var(--hairline)'),
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              color: current ? '#0A1006' : active ? '#4ADE80' : 'var(--fg-tertiary)',
              transition: 'all 220ms ease-out', position: 'relative', overflow: 'hidden',
            }}>
              {current && <span className="sweep-mask" />}
              <Icon name={phase > i || done ? 'check' : p.icon} size={11} stroke={2} />
            </span>
            <span className="micro" style={{ fontSize: 8.5, color: active ? '#4ADE80' : 'var(--fg-tertiary)', letterSpacing: '0.12em' }}>{p.label}</span>
          </div>
          {i < PHASES.length - 1 && (
            <div style={{ flex: 1, height: 1, background: phase > i ? '#4ADE80' : 'var(--hairline)', boxShadow: phase > i ? '0 0 4px #4ADE80' : 'none', transition: 'all 320ms ease-out' }} />
          )}
        </React.Fragment>;
      })}
    </div>

    {/* Streaming log */}
    <div ref={scrollRef} style={{
      flex: 1, padding: 14, fontFamily: 'var(--font-mono)', fontSize: 11.5, lineHeight: 1.55,
      color: 'var(--fg-secondary)', overflowY: 'auto',
      maxHeight: layout.live.h - 220,
    }}>
      {events.map((e, i) => (
        <div key={i} className="log-row" style={{ display: 'grid', gridTemplateColumns: '48px 60px 1fr', columnGap: 10, marginBottom: 3 }}>
          <span style={{ color: 'var(--fg-quaternary)' }}>{(e.ms/1000).toFixed(2)}</span>
          <span style={{ color: 'var(--fg-tertiary)' }}>[{PHASES[e.ph].id}]</span>
          <span style={{ color: kindColor(e.k), wordBreak: 'break-word' }}>
            {e.k === 'task' && '↳ '}{e.k === 'tool' && '· '}{e.k === 'ok' && '✓ '}{e.k === 'note' && '› '}
            {e.t}
            {e.s && <div style={{ paddingLeft: 14, color: 'var(--fg-tertiary)', fontSize: 11, marginTop: 1 }}>{e.s}</div>}
          </span>
        </div>
      ))}
      {!done && events.length > 0 && <span className="caret" />}
    </div>

    {/* Footer summary */}
    <div style={{ padding: '10px 14px', borderTop: '1px solid var(--hairline-soft)', display: 'flex', gap: 16, alignItems: 'center', fontSize: 11 }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--fg-secondary)' }}>
        <Icon name="cpu" size={11} /> 14 tools
      </span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--fg-secondary)' }}>
        <Icon name="dollar-sign" size={11} /> $0.0014
      </span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--fg-secondary)' }}>
        <Icon name="timer" size={11} /> {((events.at(-1)?.ms || 0)/1000).toFixed(2)}s
      </span>
      <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--fg-tertiary)' }}>
        <Icon name="shield-check" size={11} /> Paper · not advice
      </span>
    </div>
  </ArtifactCard>;
}

/* ================================================================
   6 · PROPOSED ORDERS — trade tickets ready for approval
   ================================================================ */
const ORDERS = [
  { sym: 'NVDA', side: 'BUY',  qty: 28, px: 178.40, stop: 168.20, tgt: 196.00, conf: 84 },
  { sym: 'AVGO', side: 'BUY',  qty: 3,  px: 1842.10, stop: 1762.50, tgt: 1948.00, conf: 78 },
  { sym: 'AMD',  side: 'TRIM', qty: 6,  px: 448.81, stop: null,   tgt: 478.00, conf: 71 },
];

function OrdersCard({ layout }) {
  return <ArtifactCard id="orders" layout={layout}
    kicker="PROPOSED ORDERS · AWAITING APPROVAL"
    title="3 trades · $7,824 notional"
    icon="circle-check-big"
    badge={
      <button style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        padding: '4px 9px', borderRadius: 99, border: 0,
        background: 'var(--agent-grad)', color: '#0A1006',
        fontSize: 10.5, fontWeight: 600, letterSpacing: '0.04em', cursor: 'pointer',
        fontFamily: 'inherit',
      }}>
        <Icon name="check" size={10} stroke={2.5} /> APPROVE ALL
      </button>
    }>
    <div className="artifact-body" style={{ paddingTop: 4 }}>
      {ORDERS.map((o, i) => (
        <div key={o.sym} className="slide-up" style={{
          padding: '10px 0', borderBottom: i === ORDERS.length - 1 ? 0 : '1px solid var(--hairline-soft)',
          animationDelay: i * 60 + 'ms',
        }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 9.5, fontWeight: 700,
              padding: '2px 7px', borderRadius: 4, letterSpacing: '0.08em',
              background: o.side === 'BUY' ? 'rgba(34,197,94,0.16)' : o.side === 'TRIM' ? 'rgba(245,193,71,0.16)' : 'rgba(239,68,68,0.16)',
              color: o.side === 'BUY' ? '#4ADE80' : o.side === 'TRIM' ? '#F5C147' : '#F87171',
            }}>{o.side}</span>
            <span className="mono" style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)' }}>{o.qty}</span>
            <span className="mono" style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-primary)', letterSpacing: '0.03em' }}>{o.sym}</span>
            <span className="mono" style={{ fontSize: 11.5, color: 'var(--fg-secondary)' }}>@ ${o.px.toFixed(2)}</span>
            <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              <div style={{ width: 50, height: 3, borderRadius: 99, background: 'rgba(244,239,227,0.06)', overflow: 'hidden' }}>
                <div style={{ width: o.conf + '%', height: '100%', background: 'var(--agent-grad)' }} />
              </div>
              <span className="mono" style={{ fontSize: 10.5, color: '#4ADE80' }}>{o.conf}%</span>
            </span>
          </div>
          <div style={{ display: 'flex', gap: 14, fontSize: 10.5, color: 'var(--fg-tertiary)', fontFamily: 'var(--font-mono)' }}>
            <span>STOP <span style={{ color: o.stop ? '#F87171' : 'var(--fg-quaternary)' }}>{o.stop ? '$' + o.stop.toFixed(2) : '—'}</span></span>
            <span>TGT <span style={{ color: '#4ADE80' }}>${o.tgt.toFixed(2)}</span></span>
            <span style={{ marginLeft: 'auto' }}>
              <button className="btn-icon" style={{ width: 22, height: 22, border: 0, color: 'var(--fg-tertiary)' }}><Icon name="pencil" size={10} /></button>
              <button className="btn-icon" style={{ width: 22, height: 22, border: 0, color: 'var(--fg-tertiary)' }}><Icon name="x" size={10} /></button>
            </span>
          </div>
        </div>
      ))}
    </div>
  </ArtifactCard>;
}

/* ================================================================
   7 · RISK FRAME — portfolio risk metrics
   ================================================================ */
function RiskCard({ layout }) {
  return <ArtifactCard id="risk" layout={layout}
    kicker="RISK FRAME"
    title="Post-trade exposure"
    icon="shield"
    badge={<span className="mono" style={{ fontSize: 10, color: '#4ADE80' }}>WITHIN LIMITS</span>}>
    <div className="artifact-body" style={{ paddingTop: 4 }}>
      {[
        { l: 'Portfolio beta',    v: '1.34',  bar: 0.67, tone: '#F5C147' },
        { l: 'Max position',      v: '8.2%',  bar: 0.41 },
        { l: 'Sector concentration', v: '38%', bar: 0.76, tone: '#F5C147' },
        { l: 'VaR (95%, 1d)',     v: '$1,284', bar: 0.32 },
        { l: 'Tail risk hedged',  v: '38%',   bar: 0.38, tone: '#4ADE80' },
      ].map((r, i) => (
        <div key={i} className="slide-up" style={{ padding: '7px 0', borderBottom: i === 4 ? 0 : '1px solid var(--hairline-soft)', animationDelay: i*30 + 'ms' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 5 }}>
            <span style={{ color: 'var(--fg-secondary)' }}>{r.l}</span>
            <span className="mono" style={{ color: r.tone || 'var(--fg-primary)', fontWeight: 500 }}>{r.v}</span>
          </div>
          <div style={{ height: 3, background: 'rgba(244,239,227,0.05)', borderRadius: 99, overflow: 'hidden' }}>
            <div style={{ width: (r.bar * 100) + '%', height: '100%', background: r.tone || 'rgba(244,239,227,0.4)', transition: 'width 600ms ease-out' }} />
          </div>
        </div>
      ))}
    </div>
  </ArtifactCard>;
}

/* ================================================================
   8 · WATCHERS — agents observing this run
   ================================================================ */
function WatchersCard({ layout }) {
  const watchers = [
    { name: 'Risk Sentinel',  status: 'OK',     icon: 'shield' },
    { name: 'Compliance Bot', status: 'OK',     icon: 'badge-check' },
    { name: 'News Listener',  status: 'WATCH',  icon: 'antenna' },
    { name: 'Vol Tracker',    status: 'OK',     icon: 'activity' },
  ];
  return <ArtifactCard id="watchers" layout={layout}
    kicker="AGENT WATCHERS · 4"
    title="Co-running guardrails"
    icon="users"
    badge={null}>
    <div className="artifact-body" style={{ paddingTop: 4 }}>
      {watchers.map((w, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: i === watchers.length - 1 ? 0 : '1px solid var(--hairline-soft)' }}>
          <span style={{
            width: 22, height: 22, borderRadius: 6,
            background: 'rgba(244,239,227,0.04)', border: '1px solid var(--hairline)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--fg-secondary)',
          }}>
            <Icon name={w.icon} size={11} />
          </span>
          <span style={{ flex: 1, fontSize: 12, color: 'var(--fg-primary)' }}>{w.name}</span>
          <span className="mono" style={{
            fontSize: 9, letterSpacing: '0.1em', padding: '2px 6px', borderRadius: 4,
            background: w.status === 'OK' ? 'rgba(34,197,94,0.12)' : 'rgba(245,193,71,0.14)',
            color: w.status === 'OK' ? '#4ADE80' : '#F5C147',
          }}>{w.status}</span>
        </div>
      ))}
    </div>
  </ArtifactCard>;
}

/* ================================================================
   9 · HEDGE — suggested tail hedge
   ================================================================ */
function HedgeCard({ layout }) {
  return <ArtifactCard id="hedge" layout={layout}
    kicker="HEDGE PROPOSAL"
    title="Tail protection"
    icon="umbrella"
    badge={<span className="mono" style={{ fontSize: 10, color: 'var(--fg-secondary)' }}>OPTIONAL</span>}>
    <div className="artifact-body" style={{ paddingTop: 4 }}>
      <div style={{ fontSize: 12, color: 'var(--fg-secondary)', lineHeight: 1.5, marginBottom: 12 }}>
        Post-trade beta lifts to <span className="mono" style={{ color: '#F5C147' }}>1.34</span>. A modest SPY put reduces 1-day tail by 38% for 0.73% of equity.
      </div>
      <div style={{
        padding: 12, borderRadius: 10,
        background: 'rgba(74,222,128,0.04)', border: '1px solid rgba(74,222,128,0.2)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span className="mono" style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.03em' }}>SPY 580P 30d</span>
          <span className="mono" style={{ fontSize: 12, color: '#4ADE80' }}>×4</span>
        </div>
        <div style={{ display: 'flex', gap: 12, fontSize: 10.5, color: 'var(--fg-tertiary)', fontFamily: 'var(--font-mono)' }}>
          <span>PREM <span style={{ color: 'var(--fg-primary)' }}>$1.84</span></span>
          <span>COST <span style={{ color: '#F87171' }}>$736</span></span>
          <span>COVER <span style={{ color: '#4ADE80' }}>38%</span></span>
        </div>
      </div>
      <button style={{
        marginTop: 12, width: '100%',
        padding: '8px', borderRadius: 8,
        background: 'transparent', border: '1px solid var(--hairline)',
        color: 'var(--fg-secondary)', fontSize: 11.5, cursor: 'pointer', fontFamily: 'inherit',
      }}>+ Add to order batch</button>
    </div>
  </ArtifactCard>;
}

/* ================================================================
   EDGES LAYER — curved svg connectors between cards
   ================================================================ */
function EdgesLayer({ layout, canvasW, canvasH }) {
  // Get anchor point on a card edge
  const anchor = (cardId, side) => {
    const L = layout[cardId];
    if (!L) return { x: 0, y: 0 };
    switch (side) {
      case 'right':  return { x: L.x + L.w, y: L.y + L.h / 2 };
      case 'left':   return { x: L.x,       y: L.y + L.h / 2 };
      case 'top':    return { x: L.x + L.w / 2, y: L.y };
      case 'bottom': return { x: L.x + L.w / 2, y: L.y + L.h };
      default: return { x: L.x, y: L.y };
    }
  };
  return <svg className="edges" width={canvasW} height={canvasH} viewBox={`0 0 ${canvasW} ${canvasH}`}>
    {EDGES.map((e, i) => {
      const [s1, s2] = e.side.split('-');
      const a = anchor(e.from, s1);
      const b = anchor(e.to, s2);
      // Cubic bezier — horizontal-ish curve
      let c1, c2;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      if (s1 === 'right' || s1 === 'left') {
        c1 = { x: a.x + dx * 0.5, y: a.y };
        c2 = { x: b.x - dx * 0.5, y: b.y };
      } else {
        c1 = { x: a.x, y: a.y + dy * 0.5 };
        c2 = { x: b.x, y: b.y - dy * 0.5 };
      }
      const d = `M${a.x},${a.y} C${c1.x},${c1.y} ${c2.x},${c2.y} ${b.x},${b.y}`;
      return <g key={i}>
        <path d={d} className={'edge' + (e.live ? ' edge-live' : '')} />
        <circle cx={a.x} cy={a.y} r="3" className={e.live ? 'edge-dot-live' : 'edge-dot'} />
        <circle cx={b.x} cy={b.y} r="3" className={e.live ? 'edge-dot-live' : 'edge-dot'} />
      </g>;
    })}
  </svg>;
}

/* ================================================================
   CANVAS — composes all artifacts on a virtual coord system that
   centers in the viewport.
   ================================================================ */
function Canvas({ layout, leftRailOpen, dotDensity }) {
  // Canvas total dimensions
  const canvasW = 1500;
  const canvasH = 860;

  const dotClass = dotDensity === 'dense' ? 'dotgrid dotgrid-dense' :
                   dotDensity === 'loose' ? 'dotgrid dotgrid-loose' : 'dotgrid';

  return <div style={{
    position: 'fixed',
    top: 80, bottom: 16,
    left: leftRailOpen ? 308 : 16,
    right: 70,
    overflow: 'hidden', borderRadius: 18,
  }} className="no-select">
    {/* Dot grid */}
    <div className={dotClass} />
    {/* Ambient blobs */}
    <div className="ambient" />

    {/* Scrolling canvas (large virtual area) */}
    <div style={{
      position: 'absolute',
      top: '50%', left: '50%',
      transform: 'translate(-50%, -50%)',
      width: canvasW, height: canvasH,
    }}>
      {/* Edges underneath */}
      <EdgesLayer layout={layout} canvasW={canvasW} canvasH={canvasH} />

      {/* Cards */}
      <BriefCard layout={layout} />
      <SectorsCard layout={layout} />
      <CandidatesCard layout={layout} />
      <BacktestCard layout={layout} />
      <LiveCard layout={layout} />
      <OrdersCard layout={layout} />
      <RiskCard layout={layout} />
      <WatchersCard layout={layout} />
      <HedgeCard layout={layout} />
    </div>

    {/* Zoom indicator (bottom-right) */}
    <div className="glass no-select" style={{
      position: 'absolute', bottom: 16, right: 16,
      display: 'flex', alignItems: 'center', gap: 4,
      padding: 4, borderRadius: 10,
    }}>
      <button className="btn-icon" style={{ width: 26, height: 26, border: 0 }} aria-label="Zoom out"><Icon name="minus" size={12} /></button>
      <span className="mono" style={{ fontSize: 11, color: 'var(--fg-secondary)', padding: '0 6px', minWidth: 36, textAlign: 'center' }}>100%</span>
      <button className="btn-icon" style={{ width: 26, height: 26, border: 0 }} aria-label="Zoom in"><Icon name="plus" size={12} /></button>
      <span style={{ width: 1, height: 16, background: 'var(--hairline)', margin: '0 2px' }} />
      <button className="btn-icon" style={{ width: 26, height: 26, border: 0 }} aria-label="Fit"><Icon name="maximize-2" size={12} /></button>
    </div>
  </div>;
}

Object.assign(window, { Canvas, CARD_LAYOUT });
