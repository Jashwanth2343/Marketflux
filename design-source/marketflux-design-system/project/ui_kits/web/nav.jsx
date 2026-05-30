/* ===================================================================
   MarketFlux UI Kit — screens.jsx
   ===================================================================
   Top-level screens: TopNav, TickerTape, Dashboard, StockDetail,
   AIScreener, AIChatPanel, and the App router that orchestrates them.
   =================================================================== */

const NAV_ITEMS = [
  { route: 'dashboard',  icon: 'layout-dashboard', label: 'Dashboard' },
  { route: 'agents',     icon: 'sparkles',         label: 'Agents' },
  { route: 'screener',   icon: 'search',           label: 'Screener' },
  { route: 'research',   icon: 'brain',            label: 'Research' },
  { route: 'portfolio',  icon: 'briefcase',        label: 'Portfolio' },
];

/* -------- TickerTape ------------------------------------------------ */
function TickerTape() {
  const items = window.MF_DATA.indices.concat(window.MF_DATA.indices);
  return <div style={{
    background: 'var(--bg-canvas)', borderBottom: '1px solid var(--border)',
    overflow: 'hidden', height: 36, display: 'flex', alignItems: 'center',
  }}>
    <div className="mf-tape" style={{
      display: 'flex', gap: 36, whiteSpace: 'nowrap',
      animation: 'mf-scroll 60s linear infinite',
      fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums', fontSize: 12,
    }}>
      {items.map((it, i) => {
        const pos = it.pct >= 0;
        const bad = it.isVol ? !pos : pos;
        return <span key={i} style={{ display: 'inline-flex', gap: 10, alignItems: 'baseline' }}>
          <span style={{ color: 'var(--fg-secondary)' }}>{it.sym}</span>
          <span style={{ color: 'var(--fg-primary)' }}>{typeof it.px === 'number' ? it.px.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : it.px}</span>
          <span style={{ color: bad ? 'var(--bull-strong)' : 'var(--bear-strong)' }}>{pos ? '▲ +' : '▼ −'}{Math.abs(it.pct).toFixed(2)}%</span>
        </span>;
      })}
    </div>
    <style>{`@keyframes mf-scroll { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }`}</style>
  </div>;
}

/* -------- TopNav ---------------------------------------------------- */
function TopNav({ route, setRoute, onOpenChat, chatOpen }) {
  return <div style={{
    position: 'sticky', top: 0, zIndex: 30,
    background: 'var(--bg-blur)', backdropFilter: 'blur(8px)',
    borderBottom: '1px solid var(--border)',
  }}>
    <TickerTape />
    <header style={{
      display: 'flex', alignItems: 'center', gap: 24,
      padding: '12px 24px', height: 60, boxSizing: 'border-box',
    }}>
      <a onClick={() => setRoute('dashboard')} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10 }}>
        <img src="../../assets/logo-mark.svg" width="28" height="28" alt="" />
        <span style={{
          fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 17,
          letterSpacing: '-0.015em', color: 'var(--fg-primary)',
        }}>Market<span style={{ color: 'var(--accent-strong)' }}>Flux</span></span>
      </a>
      <nav style={{ display: 'flex', gap: 2, marginLeft: 12 }}>
        {NAV_ITEMS.map(it => {
          const active = route === it.route;
          return <a key={it.route}
            onClick={() => setRoute(it.route)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 7,
              padding: '7px 12px', cursor: 'pointer',
              fontFamily: 'var(--font-body)', fontSize: 13,
              fontWeight: active ? 600 : 500,
              color: active ? 'var(--fg-primary)' : 'var(--fg-secondary)',
              background: active ? 'var(--bg-surface-2)' : 'transparent',
              borderRadius: 6,
            }}>
            <Icon name={it.icon} size={14} style={{ color: 'currentColor' }} />
            {it.label}
          </a>;
        })}
      </nav>
      <div style={{ flex: 1 }} />
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        background: 'var(--bg-surface-2)', border: '1px solid var(--border)',
        padding: '8px 12px', minWidth: 320, whiteSpace: 'nowrap',
        borderRadius: 6,
      }}>
        <Icon name="search" size={14} style={{ color: 'var(--fg-tertiary)', flexShrink: 0 }} />
        <span style={{ fontSize: 13, color: 'var(--fg-tertiary)' }}>Search tickers, ETFs, analysis…</span>
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-tertiary)', flexShrink: 0 }}>⌘ K</span>
      </div>
      <ThemeToggle />
      <Button variant={chatOpen ? 'primary' : 'secondary'} icon="sparkles" onClick={onOpenChat}
        style={{ whiteSpace: 'nowrap', flexShrink: 0 }}>
        {chatOpen ? 'AI open' : 'Ask FluxAI'}
      </Button>
    </header>
  </div>;
}

/* -------- ThemeToggle — cycles auto → light → dark, persisted ------- */
function applyTheme(mode) {
  const el = document.documentElement;
  if (mode === 'auto') el.removeAttribute('data-theme');
  else el.setAttribute('data-theme', mode);
}
function ThemeToggle() {
  const [mode, setMode] = useState(() => localStorage.getItem('mf-theme') || 'auto');
  useEffect(() => { applyTheme(mode); localStorage.setItem('mf-theme', mode); }, [mode]);
  const order = ['auto', 'light', 'dark'];
  const icon = mode === 'auto' ? 'monitor' : mode === 'light' ? 'sun' : 'moon';
  const next = () => setMode(order[(order.indexOf(mode) + 1) % order.length]);
  return <button onClick={next} title={`Theme: ${mode} (click to change)`} style={{
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    width: 38, height: 38, flexShrink: 0,
    background: 'transparent', border: '1px solid var(--border-strong)',
    borderRadius: 10, color: 'var(--fg-secondary)', cursor: 'pointer',
    transition: 'color var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out)',
  }}>
    <Icon name={icon} size={16} style={{ color: 'currentColor' }} />
  </button>;
}

/* -------- AI Chat Panel -------------------------------------------- */
function AIChatPanel({ open, onClose }) {
  const [draft, setDraft] = useState('');
  const [thread, setThread] = useState([
    { role: 'user', text: 'What should I research today?' },
    { role: 'ai', sym: 'NVDA', conf: 91,
      text: 'Datacenter run-rate is accelerating. Blackwell ramp is ahead of schedule. Hyperscaler AI capex remains resilient. Target: $1,400 over 12 months.' },
  ]);
  function send() {
    if (!draft.trim()) return;
    setThread(t => t.concat({ role: 'user', text: draft }));
    setDraft('');
    setTimeout(() => {
      setThread(t => t.concat({ role: 'ai', sym: 'AAPL', conf: 84,
        text: 'AAPL services revenue is inflecting and forward P/E remains reasonable. Bull case requires holding $190 support. Watch March earnings.' }));
    }, 380);
  }
  if (!open) return null;
  return <aside style={{
    position: 'fixed', top: 0, right: 0, bottom: 0,
    width: 400, zIndex: 40,
    background: 'var(--bg-surface)',
    borderLeft: '1px solid var(--border)',
    boxShadow: 'var(--shadow-elev)',
    display: 'flex', flexDirection: 'column',
  }}>
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '14px 18px', borderBottom: '1px solid var(--border)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span className="mf-live-dot mf-agent-dot" />
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 15 }}>FluxAI</span>
        <span style={{ fontSize: 11, color: 'var(--fg-tertiary)' }}>Gemini 2.5</span>
      </div>
      <a onClick={onClose} style={{ cursor: 'pointer', color: 'var(--fg-tertiary)', fontSize: 18, lineHeight: 1 }}>×</a>
    </div>
    <div style={{ flex: 1, overflow: 'auto', padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      {thread.map((m, i) => m.role === 'user' ? (
        <div key={i} style={{
          alignSelf: 'flex-end', maxWidth: '85%',
          background: 'var(--bg-surface-2)', border: '1px solid var(--border)',
          padding: '10px 12px', fontSize: 13, color: 'var(--fg-primary)',
          borderRadius: 8,
        }}>{m.text}</div>
      ) : (
        <div key={i} style={{
          alignSelf: 'flex-start', maxWidth: '95%',
          background: 'var(--bg-surface-2)',
          borderLeft: '2px solid var(--accent)',
          padding: '12px 14px',
          borderRadius: '0 8px 8px 0',
        }}>
          <div style={{ fontSize: 11, fontWeight: 500,
            color: 'var(--accent-strong)', marginBottom: 6 }}>
            {m.sym} · {m.conf}% confidence
          </div>
          <div style={{ fontSize: 13, color: 'var(--fg-primary)', lineHeight: 1.55 }}>{m.text}</div>
        </div>
      ))}
    </div>
    <div style={{ display: 'flex', gap: 8, padding: '12px 14px', borderTop: '1px solid var(--border)' }}>
      <input value={draft} onChange={e => setDraft(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && send()}
        placeholder="Ask about a ticker, sector, or thesis…"
        style={{
          flex: 1, background: 'var(--bg-surface-2)', border: '1px solid var(--border)',
          color: 'var(--fg-primary)', fontFamily: 'var(--font-body)', fontSize: 13,
          padding: '8px 12px', outline: 'none', borderRadius: 6,
        }} />
      <button onClick={send} style={{
        background: 'var(--accent)', color: 'var(--accent-fg)', border: 'none',
        padding: '8px 14px', fontFamily: 'var(--font-body)', fontSize: 12, fontWeight: 600,
        cursor: 'pointer', borderRadius: 6,
      }}>Send</button>
    </div>
  </aside>;
}

Object.assign(window, { TickerTape, TopNav, AIChatPanel, ThemeToggle });
