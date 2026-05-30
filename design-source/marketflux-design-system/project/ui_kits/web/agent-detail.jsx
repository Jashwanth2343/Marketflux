/* ===================================================================
   MarketFlux UI Kit — agent-detail.jsx
   ===================================================================
   The live agent workspace. Opens when an agent card is clicked.
     · Left/right rails of DOCKABLE widgets (close · move · re-add)
     · Center "agent brain": prompt + ANIMATED execution timeline
       that streams steps as if running live
   Champagne-gold = agent identity. Green/red = price only.
   =================================================================== */

const { useState: useStateAD, useEffect: useEffectAD, useRef: useRefAD, useMemo: useMemoAD } = React;

/* -------- Widget shell --------------------------------------------- */
function AgentWidget({ id, title, icon, side, onClose, onMove, children, dense }) {
  return <section className="mf-glass" style={{
    borderRadius: 'var(--radius-3)',
    display: 'flex', flexDirection: 'column',
    overflow: 'hidden',
  }}>
    <header style={{
      display: 'flex', alignItems: 'center', gap: 9,
      padding: '11px 12px 11px 14px',
      borderBottom: '1px solid var(--border)',
    }}>
      <Icon name={icon} size={14} style={{ color: 'var(--accent-strong)', flexShrink: 0 }} />
      <span style={{
        fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 600,
        letterSpacing: '-0.01em', color: 'var(--fg-primary)', whiteSpace: 'nowrap',
      }}>{title}</span>
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 2 }}>
        <button onClick={() => onMove(id)} title={side === 'left' ? 'Move right' : 'Move left'}
          style={widgetIconBtn}>
          <Icon name={side === 'left' ? 'chevrons-right' : 'chevrons-left'} size={13} style={{ color: 'currentColor' }} />
        </button>
        <button onClick={() => onClose(id)} title="Close widget" style={widgetIconBtn}>
          <Icon name="x" size={13} style={{ color: 'currentColor' }} />
        </button>
      </div>
    </header>
    <div style={{ padding: dense ? '6px 8px 10px' : '12px 14px', flex: 1, minWidth: 0 }}>
      {children}
    </div>
  </section>;
}
const widgetIconBtn = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  width: 26, height: 26, background: 'transparent', border: 'none',
  borderRadius: 7, color: 'var(--fg-tertiary)', cursor: 'pointer',
  transition: 'color var(--duration-fast) var(--ease-out), background var(--duration-fast) var(--ease-out)',
};

const adKicker = {
  fontFamily: 'var(--font-mono)', fontSize: 9.5, fontWeight: 600,
  letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--fg-tertiary)',
};

/* -------- Options Hub (pro-terminal dense chain) ------------------- */
function OptionsHubBody() {
  const d = window.MF_AGENT_WIDGETS_DATA.optionsChain;
  const cell = { fontFamily: 'var(--font-mono)', fontSize: 11, fontVariantNumeric: 'tabular-nums', padding: '5px 7px', textAlign: 'right', color: 'var(--fg-secondary)' };
  const head = { ...cell, fontSize: 9, color: 'var(--fg-tertiary)', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', borderBottom: '1px solid var(--border)' };
  return <div>
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', padding: '0 6px 9px' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16, color: 'var(--fg-primary)' }}>{d.underlying}</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-primary)' }}>${d.spot.toFixed(2)}</span>
      </div>
      <span style={adKicker}>{d.expiry} · {d.dte}DTE</span>
    </div>
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 7px 4px' }}>
      <span style={{ ...adKicker, color: 'var(--bull-strong)' }}>Calls</span>
      <span style={{ ...adKicker, color: 'var(--bear-strong)' }}>Puts</span>
    </div>
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th style={{ ...head, textAlign: 'left' }}>Bid</th><th style={head}>Δ</th>
          <th style={{ ...head, textAlign: 'center', color: 'var(--fg-secondary)' }}>Strike</th>
          <th style={head}>Δ</th><th style={{ ...head, textAlign: 'right' }}>Bid</th>
        </tr>
      </thead>
      <tbody>
        {d.rows.map(r => (
          <tr key={r.strike} style={r.target ? {
            background: 'var(--accent-bg)',
            outline: '1px solid var(--accent-border)',
          } : {}}>
            <td style={{ ...cell, textAlign: 'left', color: 'var(--fg-primary)' }}>{r.cBid.toFixed(2)}</td>
            <td style={cell}>{r.cDelta.toFixed(2)}</td>
            <td style={{ ...cell, textAlign: 'center', fontWeight: 700, color: r.target ? 'var(--accent-strong)' : 'var(--fg-primary)' }}>
              {r.strike}{r.target && <span style={{ marginLeft: 4, fontSize: 8, verticalAlign: 'middle' }}>◆</span>}
            </td>
            <td style={cell}>{r.pDelta.toFixed(2)}</td>
            <td style={{ ...cell, color: 'var(--fg-primary)' }}>{r.pBid.toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
    <div style={{ marginTop: 9, display: 'flex', alignItems: 'center', gap: 7, padding: '0 6px' }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--accent)', flexShrink: 0 }} />
      <span style={{ fontSize: 11, color: 'var(--fg-secondary)' }}>Agent target — <b style={{ color: 'var(--fg-primary)' }}>585P</b> · staged</span>
    </div>
  </div>;
}

/* -------- Positions ------------------------------------------------ */
function PositionsBody() {
  const rows = window.MF_AGENT_WIDGETS_DATA.positions;
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
    {rows.map(p => (
      <div key={p.sym} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 4px', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ minWidth: 46 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: 'var(--fg-primary)' }}>{p.sym}</div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: 'var(--fg-tertiary)' }}>{p.qty} sh</div>
        </div>
        <div style={{ flex: 1, textAlign: 'right' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-primary)', fontVariantNumeric: 'tabular-nums' }}>${p.last.toFixed(2)}</div>
        </div>
        <div style={{ minWidth: 64, textAlign: 'right' }}>
          <Pct value={p.plPct} size="s" />
        </div>
      </div>
    ))}
  </div>;
}

/* -------- Cash & buying power -------------------------------------- */
function CashBody() {
  const c = window.MF_AGENT_WIDGETS_DATA.cash;
  const fmt = n => '$' + n.toLocaleString('en-US');
  const total = c.allocated + c.idle + c.settled;
  const seg = [
    { label: 'Allocated', v: c.allocated, color: 'var(--accent)' },
    { label: 'Settled',   v: c.settled,   color: 'var(--bull)' },
    { label: 'Idle',      v: c.idle,      color: 'var(--neutral)' },
  ];
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
    <div>
      <div style={adKicker}>Buying power</div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 500, color: 'var(--fg-primary)', marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>{fmt(c.buyingPower)}</div>
    </div>
    <div style={{ display: 'flex', height: 8, borderRadius: 9999, overflow: 'hidden', gap: 2 }}>
      {seg.map(s => <div key={s.label} style={{ flex: s.v, background: s.color }} />)}
    </div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      {seg.map(s => (
        <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5 }}>
          <span style={{ width: 7, height: 7, borderRadius: 2, background: s.color }} />
          <span style={{ color: 'var(--fg-secondary)' }}>{s.label}</span>
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', color: 'var(--fg-primary)' }}>{fmt(s.v)}</span>
        </div>
      ))}
    </div>
  </div>;
}

/* -------- Market context ------------------------------------------- */
function MarketBody() {
  const rows = window.MF_AGENT_WIDGETS_DATA.market;
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
    {rows.map(m => (
      <div key={m.sym} style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '7px 6px', borderRadius: 8,
        background: m.alert ? 'var(--accent-bg)' : 'transparent',
      }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, fontWeight: 600, color: m.alert ? 'var(--accent-strong)' : 'var(--fg-secondary)', minWidth: 48 }}>{m.sym}</span>
        <span style={{ flex: 1, textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-primary)', fontVariantNumeric: 'tabular-nums' }}>
          {m.px.toLocaleString('en-US', { minimumFractionDigits: 2 })}{m.unit || ''}
        </span>
        <span style={{ minWidth: 58, textAlign: 'right' }}><Pct value={m.pct} size="s" /></span>
      </div>
    ))}
    <div style={{ marginTop: 6, padding: '8px 6px 0', borderTop: '1px solid var(--border-subtle)', fontSize: 11, color: 'var(--fg-tertiary)', display: 'flex', alignItems: 'center', gap: 6 }}>
      <span className="mf-live-dot" style={{ width: 6, height: 6 }} /> Live · streaming every 60s
    </div>
  </div>;
}

/* -------- Activity log --------------------------------------------- */
const activityKindColor = { eval: 'var(--accent-strong)', data: 'var(--bull-strong)', think: 'var(--neutral-strong)', idle: 'var(--fg-tertiary)' };
function ActivityBody({ liveLines }) {
  const base = window.MF_AGENT_WIDGETS_DATA.activity;
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
    {(liveLines || []).map((l, i) => (
      <div key={'live' + i} style={{ display: 'flex', gap: 9, padding: '6px 2px', animation: 'adLogIn 360ms var(--ease-out)' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: 'var(--accent-strong)', minWidth: 52, flexShrink: 0 }}>live</span>
        <span style={{ fontSize: 11.5, color: 'var(--fg-primary)', lineHeight: 1.45 }}>{l}</span>
      </div>
    ))}
    {base.map((a, i) => (
      <div key={i} style={{ display: 'flex', gap: 9, padding: '6px 2px', borderTop: i === 0 && (liveLines && liveLines.length) ? '1px solid var(--border-subtle)' : 'none' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: 'var(--fg-tertiary)', minWidth: 52, flexShrink: 0 }}>{a.t}</span>
        <span style={{ fontSize: 11.5, color: a.kind === 'idle' ? 'var(--fg-tertiary)' : 'var(--fg-secondary)', lineHeight: 1.45 }}>
          <span style={{ color: activityKindColor[a.kind], marginRight: 6, fontFamily: 'var(--font-mono)', fontSize: 9 }}>●</span>
          {a.text}
        </span>
      </div>
    ))}
  </div>;
}

/* -------- Guardrails ----------------------------------------------- */
function GuardrailsBody() {
  const rows = window.MF_AGENT_WIDGETS_DATA.guardrails;
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
    {rows.map(g => (
      <div key={g.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Icon name="check" size={13} style={{ color: 'var(--bull-strong)', flexShrink: 0 }} />
        <span style={{ fontSize: 12, color: 'var(--fg-secondary)' }}>{g.label}</span>
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-primary)' }}>{g.value}</span>
      </div>
    ))}
  </div>;
}

/* -------- Related news -------------------------------------------- */
function NewsBody() {
  const items = [
    { tag: 'BULLISH', cls: 'bull', src: 'Reuters', t: '2m', head: 'Volatility spikes as Fed minutes signal caution' },
    { tag: 'WATCH', cls: 'warn', src: 'Bloomberg', t: '18m', head: 'SPY options volume hits 3-month high into expiry' },
  ];
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
    {items.map((n, i) => (
      <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        <Badge variant={n.cls}>{n.tag}</Badge>
        <div style={{ fontSize: 12.5, color: 'var(--fg-primary)', lineHeight: 1.4, fontWeight: 500, textWrap: 'pretty' }}>{n.head}</div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: 'var(--fg-tertiary)', display: 'flex', justifyContent: 'space-between' }}>
          <span>{n.src}</span><span>{n.t} ago</span>
        </div>
      </div>
    ))}
  </div>;
}

/* -------- Strategy P&L --------------------------------------------- */
function PnlBody() {
  const pts = [0, 4, 2, 8, 6, 12, 10, 16, 14, 22, 19, 28];
  return <div>
    <div style={adKicker}>Realised · last 30 sessions</div>
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, margin: '4px 0 10px' }}>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 500, color: 'var(--bull-strong)' }}>+$2,840</span>
      <Pct value={6.4} size="s" />
    </div>
    <Sparkline pts={pts} color="var(--bull)" height={44} width={260} />
  </div>;
}

const WIDGET_BODIES = {
  options: OptionsHubBody, positions: PositionsBody, cash: CashBody,
  market: MarketBody, activity: ActivityBody, guardrails: GuardrailsBody,
  news: NewsBody, pnl: PnlBody,
};

/* -------- Animated execution timeline ------------------------------ */
function ExecutionTimeline({ steps, phase, activeStep, logsByStep }) {
  return <div style={{ display: 'flex', flexDirection: 'column' }}>
    {steps.map((s, i) => {
      const status = i < activeStep ? 'done' : i === activeStep ? (phase === 'done' ? 'done' : 'running') : 'pending';
      const last = i === steps.length - 1;
      return <div key={i} style={{ display: 'flex', gap: 14 }}>
        {/* rail */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 26, flexShrink: 0 }}>
          <div style={{
            width: 26, height: 26, borderRadius: 9999, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: status === 'done' ? 'var(--accent)' : status === 'running' ? 'var(--accent-bg)' : 'var(--bg-surface-2)',
            border: '1px solid ' + (status === 'pending' ? 'var(--border-strong)' : 'var(--accent-border)'),
            boxShadow: status === 'running' ? '0 0 0 4px var(--accent-bg)' : 'none',
            transition: 'all var(--duration-base) var(--ease-out)',
          }}>
            {status === 'done'
              ? <Icon name="check" size={13} style={{ color: 'var(--accent-fg)' }} />
              : status === 'running'
                ? <span className="ad-spin" style={{ width: 11, height: 11, borderRadius: 9999, border: '2px solid var(--accent-strong)', borderTopColor: 'transparent', display: 'block' }} />
                : <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-tertiary)' }}>{String(i + 1).padStart(2, '0')}</span>}
          </div>
          {!last && <div style={{
            width: 2, flex: 1, minHeight: 22,
            background: i < activeStep ? 'var(--accent)' : 'var(--border)',
            transition: 'background var(--duration-base) var(--ease-out)',
          }} />}
        </div>
        {/* content */}
        <div style={{ paddingBottom: last ? 0 : 18, flex: 1, minWidth: 0, opacity: status === 'pending' ? 0.5 : 1, transition: 'opacity var(--duration-base) var(--ease-out)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: 14.5, fontWeight: 600, color: 'var(--fg-primary)', letterSpacing: '-0.01em' }}>{s.label}</span>
            {status === 'running' && <span style={{ ...adKicker, color: 'var(--accent-strong)' }}>running</span>}
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--fg-secondary)', marginTop: 2 }}>{s.detail}</div>
          {/* streaming log */}
          {(logsByStep[i] && logsByStep[i].length > 0) && (
            <div style={{
              marginTop: 9, padding: '8px 11px', borderRadius: 10,
              background: 'var(--bg-canvas)', border: '1px solid var(--border)',
              display: 'flex', flexDirection: 'column', gap: 4,
            }}>
              {logsByStep[i].map((line, li) => (
                <div key={li} style={{ display: 'flex', gap: 8, alignItems: 'baseline', animation: 'adLogIn 320ms var(--ease-out)' }}>
                  <span style={{ color: 'var(--accent-strong)', fontFamily: 'var(--font-mono)', fontSize: 10 }}>›</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-secondary)', lineHeight: 1.5 }}>{line}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>;
    })}
  </div>;
}

/* -------- Add-widget menu ------------------------------------------ */
function AddWidgetMenu({ available, onAdd }) {
  const [open, setOpen] = useStateAD(false);
  if (available.length === 0) return null;
  return <div style={{ position: 'relative' }}>
    <button onClick={() => setOpen(o => !o)} style={{
      display: 'inline-flex', alignItems: 'center', gap: 7, padding: '8px 13px',
      background: 'var(--bg-surface-2)', border: '1px solid var(--border-strong)',
      borderRadius: 10, color: 'var(--fg-primary)', cursor: 'pointer',
      fontFamily: 'var(--font-body)', fontSize: 12.5, fontWeight: 600,
    }}>
      <Icon name="plus" size={14} style={{ color: 'var(--accent-strong)' }} /> Add widget
    </button>
    {open && <>
      <div onClick={() => setOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 40 }} />
      <div className="mf-glass" style={{
        position: 'absolute', top: 'calc(100% + 8px)', right: 0, zIndex: 41,
        width: 240, padding: 6, borderRadius: 14, display: 'flex', flexDirection: 'column', gap: 2,
      }}>
        {available.map(w => (
          <button key={w.id} onClick={() => { onAdd(w.id); setOpen(false); }} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '9px 10px',
            background: 'transparent', border: 'none', borderRadius: 9, cursor: 'pointer',
            color: 'var(--fg-primary)', fontFamily: 'var(--font-body)', fontSize: 13, textAlign: 'left',
          }}
          onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-surface-2)'}
          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
            <Icon name={w.icon} size={15} style={{ color: 'var(--accent-strong)' }} />
            {w.title}
          </button>
        ))}
      </div>
    </>}
  </div>;
}

/* -------- Agent Detail (orchestrator) ------------------------------ */
const LS_WIDGETS = 'mf-agent-widgets-v1';
function loadWidgetLayout() {
  try {
    const raw = localStorage.getItem(LS_WIDGETS);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return window.MF_AGENT_WIDGET_CATALOG.filter(w => w.default).map(w => ({ id: w.id, side: w.side }));
}

function AgentDetail({ agent, onBack }) {
  const catalog = window.MF_AGENT_WIDGET_CATALOG;
  const catById = useMemoAD(() => Object.fromEntries(catalog.map(w => [w.id, w])), []);
  const [layout, setLayout] = useStateAD(loadWidgetLayout);
  useEffectAD(() => { try { localStorage.setItem(LS_WIDGETS, JSON.stringify(layout)); } catch (e) {} }, [layout]);

  const steps = window.MF_AGENT_RUNS[agent.id] || window.MF_AGENT_RUNS.default;

  // ---- animated run state machine ----
  const events = useMemoAD(() => {
    const ev = [];
    steps.forEach((s, si) => {
      (s.log || []).forEach(line => ev.push({ type: 'log', si, line }));
      ev.push({ type: 'done', si });
    });
    return ev;
  }, [agent.id]);

  const [activeStep, setActiveStep] = useStateAD(0);
  const [logsByStep, setLogsByStep] = useStateAD({});
  const [phase, setPhase] = useStateAD('running'); // running | paused | done
  const [liveActivity, setLiveActivity] = useStateAD([]);
  const evtIdx = useRefAD(0);
  const timer = useRefAD(null);

  function resetRun() {
    if (timer.current) clearInterval(timer.current);
    evtIdx.current = 0;
    setActiveStep(0); setLogsByStep({}); setLiveActivity([]); setPhase('running');
  }

  useEffectAD(() => { resetRun(); }, [agent.id]);

  useEffectAD(() => {
    if (phase !== 'running') return;
    timer.current = setInterval(() => {
      const ev = events[evtIdx.current];
      if (!ev) { clearInterval(timer.current); setPhase('done'); return; }
      if (ev.type === 'log') {
        setLogsByStep(prev => ({ ...prev, [ev.si]: [...(prev[ev.si] || []), ev.line] }));
        setLiveActivity(prev => [ev.line, ...prev].slice(0, 4));
      } else {
        setActiveStep(ev.si + 1);
      }
      evtIdx.current += 1;
    }, 850);
    return () => clearInterval(timer.current);
  }, [phase, events]);

  // ---- widget docking ----
  const open = layout.map(l => l.id);
  const available = catalog.filter(w => !open.includes(w.id));
  const closeWidget = id => setLayout(l => l.filter(x => x.id !== id));
  const moveWidget = id => setLayout(l => l.map(x => x.id === id ? { ...x, side: x.side === 'left' ? 'right' : 'left' } : x));
  const addWidget = id => setLayout(l => [...l, { id, side: catById[id].side }]);
  const leftIds = layout.filter(l => l.side === 'left');
  const rightIds = layout.filter(l => l.side === 'right');

  const renderRail = ids => ids.map(({ id, side }) => {
    const c = catById[id]; const Body = WIDGET_BODIES[id];
    const dense = id === 'options';
    return <AgentWidget key={id} id={id} title={c.title} icon={c.icon} side={side}
      onClose={closeWidget} onMove={moveWidget} dense={dense}>
      {id === 'activity' ? <ActivityBody liveLines={liveActivity} /> : <Body />}
    </AgentWidget>;
  });

  const runStatus = phase === 'done' ? 'Run complete · monitoring' : 'Executing live';

  return <div className="mf-agent-detail" style={{ padding: '20px 24px 64px', maxWidth: 1480, margin: '0 auto' }}>
    {/* Header */}
    <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', marginBottom: 22 }}>
      <button onClick={onBack} style={{
        display: 'inline-flex', alignItems: 'center', gap: 7, padding: '8px 13px',
        background: 'transparent', border: '1px solid var(--border-strong)', borderRadius: 10,
        color: 'var(--fg-secondary)', cursor: 'pointer', fontFamily: 'var(--font-body)', fontSize: 12.5, fontWeight: 500,
      }}>
        <Icon name="arrow-left" size={14} style={{ color: 'currentColor' }} /> Agents
      </button>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, minWidth: 0 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 12, flexShrink: 0,
          background: 'var(--accent-bg)', border: '1px solid var(--accent-border)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name="sparkles" size={19} style={{ color: 'var(--accent-strong)' }} />
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 20, letterSpacing: '-0.015em', color: 'var(--fg-primary)' }}>{agent.title}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: 'var(--fg-tertiary)' }}>
            <span className={'mf-live-dot' + (phase === 'done' ? ' mf-agent-dot' : '')} style={{ width: 6, height: 6 }} />
            {runStatus} · {agent.runs} total runs
          </div>
        </div>
      </div>
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
        <button onClick={() => setPhase(p => p === 'running' ? 'paused' : 'running')} style={{
          display: 'inline-flex', alignItems: 'center', gap: 7, padding: '8px 13px',
          background: 'transparent', border: '1px solid var(--border-strong)', borderRadius: 10,
          color: 'var(--fg-primary)', cursor: 'pointer', fontFamily: 'var(--font-body)', fontSize: 12.5, fontWeight: 600,
        }}>
          <Icon name={phase === 'running' ? 'pause' : 'play'} size={13} style={{ color: 'currentColor' }} />
          {phase === 'running' ? 'Pause' : phase === 'done' ? 'Done' : 'Resume'}
        </button>
        <button onClick={resetRun} style={{
          display: 'inline-flex', alignItems: 'center', gap: 7, padding: '8px 13px',
          background: 'var(--accent)', border: 'none', borderRadius: 10,
          color: 'var(--accent-fg)', cursor: 'pointer', fontFamily: 'var(--font-body)', fontSize: 12.5, fontWeight: 600,
        }}>
          <Icon name="rotate-ccw" size={13} style={{ color: 'currentColor' }} /> Re-run
        </button>
        <AddWidgetMenu available={available} onAdd={addWidget} />
      </div>
    </div>

    {/* 3-zone workspace */}
    <div className="mf-agent-grid" style={{
      display: 'grid',
      gridTemplateColumns: (leftIds.length ? 'minmax(248px, 280px) ' : '') + 'minmax(0, 1fr)' + (rightIds.length ? ' minmax(300px, 360px)' : ''),
      gap: 16, alignItems: 'start',
    }}>
      {/* LEFT rail */}
      {leftIds.length > 0 && <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>{renderRail(leftIds)}</div>}

      {/* CENTER — agent brain */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
        {/* Prompt card */}
        <section className="mf-glass mf-glass-hi" style={{ borderRadius: 'var(--radius-3)', padding: '22px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span style={adKicker}>Plain-English strategy</span>
            <span style={{ marginLeft: 'auto' }}><Badge variant="agent" dot>FluxAI · compiled</Badge></span>
          </div>
          <p style={{
            margin: 0, fontFamily: 'var(--font-serif)', fontSize: 'clamp(20px, 2vw, 26px)',
            lineHeight: 1.3, letterSpacing: '-0.01em', color: 'var(--fg-primary)', textWrap: 'pretty',
          }}>“{agent.prompt}”</p>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 16 }}>
            {agent.tags.map(t => (
              <span key={t} style={{
                fontSize: 11, color: 'var(--fg-secondary)', padding: '3px 10px', borderRadius: 9999,
                background: 'var(--bg-surface-2)', border: '1px solid var(--border)',
              }}>{t}</span>
            ))}
          </div>
        </section>

        {/* Execution timeline */}
        <section className="mf-glass" style={{ borderRadius: 'var(--radius-3)', padding: '20px 22px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18 }}>
            <Icon name="git-branch" size={15} style={{ color: 'var(--accent-strong)' }} />
            <span style={{ fontFamily: 'var(--font-display)', fontSize: 15, fontWeight: 600, color: 'var(--fg-primary)' }}>Execution timeline</span>
            <span style={{ marginLeft: 'auto', ...adKicker }}>
              {Math.min(activeStep, steps.length)}/{steps.length} steps
            </span>
          </div>
          <ExecutionTimeline steps={steps} phase={phase} activeStep={activeStep} logsByStep={logsByStep} />
          {phase === 'done' && (
            <div className="mf-glass-bull" style={{
              marginTop: 18, padding: '12px 16px', borderRadius: 12,
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <Icon name="check-circle-2" size={17} style={{ color: 'var(--accent-strong)' }} />
              <span style={{ fontSize: 13, color: 'var(--fg-primary)', fontWeight: 500 }}>
                Run complete. Agent is now monitoring for the next trigger.
              </span>
            </div>
          )}
        </section>
      </div>

      {/* RIGHT rail */}
      {rightIds.length > 0 && <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>{renderRail(rightIds)}</div>}
    </div>

    <style>{`
      @keyframes adLogIn { from { opacity: 0; transform: translateY(3px); } to { opacity: 1; transform: none; } }
      @keyframes adSpin { to { transform: rotate(360deg); } }
      .ad-spin { animation: adSpin 0.8s linear infinite; }
      .mf-agent-detail [title]:hover { color: var(--fg-primary); }
      @media (max-width: 1080px) {
        .mf-agent-grid { grid-template-columns: 1fr !important; }
      }
    `}</style>
  </div>;
}

Object.assign(window, { AgentDetail });
