/* MarketFlux · Trading Copilot · chrome (nav, ticker, page header, tabs) */
const { useState, useEffect, useRef, useMemo } = React;

/* ------ Lucide icon wrapper ------ */
function Icon({ name, size = 16, color = 'currentColor', style = {} }) {
  const ref = useRef(null);
  useEffect(() => {
    if (window.lucide && ref.current) {
      ref.current.innerHTML = '';
      const i = document.createElement('i');
      i.setAttribute('data-lucide', name);
      ref.current.appendChild(i);
      window.lucide.createIcons({ attrs: { width: size, height: size, 'stroke-width': 1.75 } });
    }
  }, [name, size]);
  return <span ref={ref} style={{ display: 'inline-flex', width: size, height: size, color, ...style }} />;
}

/* ------ Top nav ------ */
function TopNav() {
  const routes = [
    { id: 'dashboard',   label: 'DASHBOARD',   icon: 'layout-dashboard' },
    { id: 'intel',       label: 'INTELLIGENCE',icon: 'brain' },
    { id: 'copilot',     label: 'COPILOT',     icon: 'plane' },
    { id: 'backtest',    label: 'BACKTEST',    icon: 'flask-conical' },
    { id: 'portfolio',   label: 'PORTFOLIO',   icon: 'briefcase' },
    { id: 'leaderboard', label: 'LEADERBOARD', icon: 'trophy' },
  ];
  return <header style={{
    position: 'sticky', top: 0, zIndex: 40,
    backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
    background: 'rgba(12,11,9,0.78)', borderBottom: '1px solid var(--border)',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 24, padding: '0 24px', height: 56 }}>
      {/* wordmark */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
        <Icon name="activity" size={18} color="var(--bull-strong)" />
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 15, letterSpacing: '-0.01em' }}>
          Market<span style={{ color: 'var(--bull-strong)' }}>Flux</span>
        </span>
      </div>
      {/* market status pill */}
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 7,
        padding: '4px 10px', borderRadius: 9999, border: '1px solid var(--border)',
        fontSize: 11, color: 'var(--fg-secondary)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em',
      }}>
        <span className="live-dot" />
        MARKET OPEN · 14:32 ET
      </span>

      {/* nav */}
      <nav style={{ display: 'flex', gap: 4, marginLeft: 12 }}>
        {routes.map(r => {
          const active = r.id === 'copilot';
          return <a key={r.id} style={{
            display: 'inline-flex', alignItems: 'center', gap: 7,
            padding: '7px 12px', borderRadius: 8, fontSize: 12, fontWeight: 500,
            letterSpacing: '0.06em',
            color: active ? 'var(--bull-strong)' : 'var(--fg-secondary)',
            background: active ? 'var(--bull-bg)' : 'transparent',
            border: '1px solid ' + (active ? 'var(--bull-border)' : 'transparent'),
            cursor: 'pointer',
          }}>
            <Icon name={r.icon} size={13} />
            {r.label}
          </a>;
        })}
      </nav>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '7px 12px', borderRadius: 8,
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          minWidth: 240,
        }}>
          <Icon name="search" size={13} color="var(--fg-tertiary)" />
          <input style={{
            background: 'transparent', border: 0, outline: 'none', color: 'var(--fg-secondary)',
            fontSize: 12, flex: 1, fontFamily: 'inherit',
          }} placeholder="Search ticker, news, agents…" />
          <span className="mono" style={{ fontSize: 10, color: 'var(--fg-tertiary)', border: '1px solid var(--border)', borderRadius: 4, padding: '1px 6px' }}>⌘K</span>
        </div>
        <button style={{
          padding: '7px 14px', borderRadius: 8,
          background: 'var(--bull)', color: '#0C0B09', border: 0,
          fontSize: 12, fontWeight: 600, letterSpacing: '0.04em', cursor: 'pointer',
        }}>SIGN IN</button>
      </div>
    </div>
  </header>;
}

/* ------ Ticker tape ------ */
const TICKER_DATA = [
  { sym: 'S&P 500',   val: '5,892.40',  d: +38.21,  pct: +0.65 },
  { sym: 'NASDAQ 100',val: '29,444.20', d: +78.90,  pct: +0.27 },
  { sym: 'DOW',       val: '42,318.55', d: -112.04, pct: -0.26 },
  { sym: 'VIX',       val: '14.28',     d: -0.42,   pct: -2.86 },
  { sym: 'US10Y',     val: '4.182%',    d: -0.024,  pct: -0.57 },
  { sym: 'DXY',       val: '104.62',    d: +0.18,   pct: +0.17 },
  { sym: 'BTC',       val: '76,694',    d: +1243,   pct: +1.65 },
  { sym: 'ETH',       val: '2,124.90',  d: +60.70,  pct: +2.94 },
  { sym: 'GOLD',      val: '2,648.30',  d: +12.20,  pct: +0.46 },
  { sym: 'WTI',       val: '71.42',     d: -0.88,   pct: -1.22 },
];
function TickerTape() {
  const row = (i) => TICKER_DATA.map((t, j) => {
    const pos = t.d >= 0;
    return <span key={i+'-'+j} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '0 22px', borderRight: '1px solid var(--border-subtle)' }}>
      <span className="micro" style={{ color: 'var(--fg-secondary)' }}>{t.sym}</span>
      <span className="mono" style={{ fontSize: 12, color: 'var(--fg-primary)' }}>{t.val}</span>
      <span className="mono" style={{ fontSize: 11, color: pos ? 'var(--bull-strong)' : 'var(--bear-strong)' }}>
        {pos ? '▲' : '▼'} {pos ? '+' : '−'}{Math.abs(t.d).toLocaleString('en-US', { maximumFractionDigits: 2 })} ({pos ? '+' : '−'}{Math.abs(t.pct).toFixed(2)}%)
      </span>
    </span>;
  });
  return <div style={{
    overflow: 'hidden', whiteSpace: 'nowrap',
    borderBottom: '1px solid var(--border)',
    height: 36, display: 'flex', alignItems: 'center',
    background: 'var(--bg-canvas)',
  }}>
    <div className="ticker-track" style={{ display: 'inline-flex' }}>
      {row(0)}{row(1)}
    </div>
  </div>;
}

/* ------ Page header + tabs ------ */
function PageHeader({ tab, setTab }) {
  const tabs = [
    { id: 'agent',     label: 'Copilot Agent',  icon: 'plane',     count: 1, active: true },
    { id: 'studio',    label: 'Strategy Studio',icon: 'wand-sparkles' },
    { id: 'autopilot', label: 'Auto-Pilot',     icon: 'list-checks' },
    { id: 'paper',     label: 'Paper Portfolio',icon: 'wallet' },
  ];
  return <section style={{ padding: '28px 32px 0', maxWidth: 1480, margin: '0 auto', width: '100%' }}>
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24, flexWrap: 'wrap' }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <span className="kicker">Trading · Autonomous</span>
          <span style={{ width: 3, height: 3, borderRadius: 99, background: 'var(--border-strong)' }} />
          <span className="kicker" style={{ color: 'var(--bull-strong)' }}>Paper account</span>
        </div>
        <h1 style={{
          margin: 0, fontFamily: 'var(--font-display)', fontWeight: 600,
          fontSize: 40, letterSpacing: '-0.025em', lineHeight: 1.05,
        }}>
          Trading Copilot
        </h1>
        <p style={{ margin: '10px 0 0', fontSize: 15, color: 'var(--fg-secondary)', maxWidth: 560, lineHeight: 1.55 }}>
          Plain-English research and paper trade execution.
          Every step is shown — every order is yours to approve.
        </p>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button style={{
          display: 'inline-flex', alignItems: 'center', gap: 7, padding: '8px 12px',
          background: 'transparent', color: 'var(--fg-secondary)',
          border: '1px solid var(--border)', borderRadius: 8, fontSize: 12, cursor: 'pointer',
        }}>
          <Icon name="book-open" size={13} /> Read the brief
        </button>
        <button style={{
          display: 'inline-flex', alignItems: 'center', gap: 7, padding: '8px 12px',
          background: 'transparent', color: 'var(--fg-secondary)',
          border: '1px solid var(--border)', borderRadius: 8, fontSize: 12, cursor: 'pointer',
        }}>
          <Icon name="clock" size={13} /> History · 24
        </button>
      </div>
    </div>

    {/* Tab strip */}
    <div style={{
      marginTop: 28, borderBottom: '1px solid var(--border)',
      display: 'flex', gap: 4, alignItems: 'flex-end',
    }}>
      {tabs.map(t => {
        const active = t.id === tab;
        return <button key={t.id} onClick={() => setTab(t.id)} style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '12px 14px',
          background: 'transparent', border: 0, cursor: 'pointer',
          color: active ? 'var(--fg-primary)' : 'var(--fg-tertiary)',
          fontSize: 13, fontWeight: 500,
          borderBottom: '2px solid ' + (active ? 'var(--bull-strong)' : 'transparent'),
          marginBottom: -1,
          position: 'relative',
        }}>
          <Icon name={t.icon} size={14} color={active ? 'var(--bull-strong)' : 'var(--fg-tertiary)'} />
          {t.label}
          {t.count && <span className="mono" style={{
            fontSize: 10, padding: '1px 6px', borderRadius: 99,
            background: active ? 'var(--bull-bg)' : 'var(--bg-surface)',
            color: active ? 'var(--bull-strong)' : 'var(--fg-tertiary)',
            border: '1px solid ' + (active ? 'var(--bull-border)' : 'var(--border)'),
          }}>{t.count}</span>}
        </button>;
      })}
    </div>
  </section>;
}

Object.assign(window, { Icon, TopNav, TickerTape, PageHeader });
