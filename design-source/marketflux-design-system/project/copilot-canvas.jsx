/* MarketFlux · Trading Copilot · canvas (idle → running → proposal) */

/* === Prompt presets =============================================== */
const PROMPTS = [
  {
    id: 'momentum',
    text: 'Buy $5,000 of the strongest large-cap momentum name',
    ticker: 'NVDA',
    icon: 'trending-up',
    action: 'BUY',
    qty: 28, price: 178.40, stop: 168.20, target: 196.00,
    confidence: 84,
    rationale: 'NVDA reclaimed 20-EMA on 1.6× avg volume with constructive options skew. Momentum cohort screening top-decile vs SPX over 5/21d.',
  },
  {
    id: 'review',
    text: 'Review my portfolio and tell me what to trim or add',
    ticker: 'AMD',
    icon: 'activity',
    action: 'TRIM',
    qty: 6, price: 448.81, stop: null, target: 478.00,
    confidence: 71,
    rationale: 'AMD has run +18% MTD against tightening sector breadth. Trimming 33% protects ~$280 of unrealized P&L while keeping core thesis.',
  },
  {
    id: 'risk',
    text: 'What is my biggest risk right now, and how would you hedge it?',
    ticker: 'SPY',
    icon: 'shield',
    action: 'HEDGE',
    qty: 4, price: 587.20, stop: null, target: 575.00,
    confidence: 68,
    rationale: 'Portfolio beta to QQQ = 1.34. A 4-lot SPY 30d 580P at 1.84 reduces tail by ~38% for ~$736 premium (0.73% of equity).',
  },
  {
    id: 'profit',
    text: 'Take profit on any position up more than 10% this week',
    ticker: 'AAPL',
    icon: 'target',
    action: 'SELL',
    qty: 5, price: 279.96, stop: null, target: null,
    confidence: 92,
    rationale: 'AAPL position closed the week +14.4%. Locking gains aligns with stated rule. No active catalysts before earnings (18d out).',
  },
  {
    id: 'swing',
    text: 'Find a high-conviction swing trade for this week',
    ticker: 'TSLA',
    icon: 'zap',
    action: 'BUY',
    qty: 8, price: 342.60, stop: 328.40, target: 368.00,
    confidence: 76,
    rationale: 'TSLA broke a 6-week base on increasing volume. 21-day ATR supports a $14 stop. Risk/reward 1.79× over 5-10 day horizon.',
  },
];

/* === Scripted log timeline per prompt ============================ */
function buildScript(p) {
  // Each entry: { at_ms, phase, kind, text, sub?, value? }
  const t = (ms, phase, kind, text, sub) => ({ at_ms: ms, phase, kind, text, sub });
  return [
    t(   0, 0, 'sys',  '$ flux.run --agent=copilot --mode=paper'),
    t( 120, 0, 'task', 'intent.parse',                            'horizon ← 5–21d · capital ← $5,000 · risk ← medium'),
    t( 380, 0, 'ok',   'intent ✓',                                '142ms'),
    t( 500, 1, 'task', 'alpaca.account.read',                     'cash=$90,520.19 · bp=$181,040.38 · positions=2'),
    t( 820, 1, 'ok',   'context ✓',                               '78ms'),
    t( 980, 2, 'task', 'market.quote("' + p.ticker + '")',        'last=$' + p.price.toFixed(2) + ' · vol=1.4× avg'),
    t(1180, 2, 'tool', 'indicators.compute',                      'RSI(14) · MACD · EMA(20/50) · ATR(14)'),
    t(1420, 2, 'tool', 'news.scan('+ p.ticker +', 24h)',          '14 items · net sentiment +0.42'),
    t(1700, 2, 'tool', 'fundamentals.peek',                       'NTM P/E=28.2 · ER in 18d · guide raised'),
    t(2000, 2, 'tool', 'peers.compare',                           '5 peers · relative strength rank 1/5'),
    t(2300, 2, 'ok',   'research ✓',                              '1.32s · 14 signals fused'),
    t(2520, 3, 'task', 'risk.size(0.8% portfolio)',               'kelly_frac=0.42 · ATR-scaled stop'),
    t(2880, 3, 'ok',   'sizing ✓',                                'qty=' + p.qty + ' · stop -3.8% · target +5.6%'),
    t(3120, 4, 'task', 'proposal.compose',                        p.action + ' ' + p.qty + ' ' + p.ticker + ' @ market'),
    t(3380, 4, 'note', '"' + p.rationale + '"'),
    t(3700, 4, 'ok',   'ready for review',                        'awaiting your approval'),
  ];
}

/* === Idle command bar ============================================ */
function CommandBar({ onRun }) {
  const [val, setVal] = useState('');
  return <form onSubmit={e => { e.preventDefault(); if (val.trim()) onRun({
    id: 'custom', text: val, ticker: 'SPY', icon: 'sparkles', action: 'BUY',
    qty: 8, price: 587.20, stop: 575.00, target: 605.00, confidence: 72,
    rationale: val,
  });}}
  style={{
    display: 'flex', alignItems: 'center', gap: 12,
    background: 'var(--bg-surface)', border: '1px solid var(--border-strong)',
    borderRadius: 12, padding: '14px 16px',
  }}>
    <span className="mono" style={{ color: 'var(--bull-strong)', fontSize: 13 }}>›</span>
    <input value={val} onChange={e => setVal(e.target.value)}
      placeholder="Tell the copilot what to do…"
      style={{
        flex: 1, background: 'transparent', border: 0, outline: 'none',
        fontSize: 15, color: 'var(--fg-primary)', fontFamily: 'inherit',
      }} />
    <span className="micro" style={{ color: 'var(--fg-tertiary)' }}>↵ run</span>
    <button type="submit" style={{
      display: 'inline-flex', alignItems: 'center', gap: 7,
      padding: '8px 14px', borderRadius: 8,
      background: 'var(--bull)', color: '#0C0B09', border: 0,
      fontSize: 12, fontWeight: 600, letterSpacing: '0.04em', cursor: 'pointer',
    }}>
      <Icon name="play" size={12} /> RUN AGENT
    </button>
  </form>;
}

/* === Idle state ================================================== */
function IdleCanvas({ onRun }) {
  return <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
    {/* Hero band */}
    <div style={{
      position: 'relative', flex: '0 0 auto',
      padding: '40px 32px 28px',
      borderBottom: '1px solid var(--border)',
      overflow: 'hidden',
    }}>
      <div className="grid-bg" style={{ position: 'absolute', inset: 0, opacity: 0.55, pointerEvents: 'none' }} />

      <div style={{ position: 'relative', display: 'flex', gap: 28, alignItems: 'center', maxWidth: 880, margin: '0 auto', textAlign: 'center', flexDirection: 'column' }}>
        {/* Orb */}
        <div className="orb" style={{
          width: 76, height: 76, borderRadius: 18,
          background: 'radial-gradient(circle at 30% 30%, rgba(74,222,128,0.45), rgba(34,197,94,0.04) 70%)',
          border: '1px solid var(--bull-border)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--bull-strong)',
        }}>
          <Icon name="plane" size={32} />
        </div>

        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '4px 10px', borderRadius: 99, border: '1px solid var(--border)', background: 'var(--bg-surface)', marginBottom: 14 }}>
            <span className="live-dot" />
            <span className="micro" style={{ color: 'var(--fg-secondary)' }}>STANDING BY · GEMINI 2.5 FLASH</span>
          </div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 30, letterSpacing: '-0.02em', lineHeight: 1.1 }}>
            What should we look at next<span className="caret" />
          </div>
          <div style={{ marginTop: 10, fontSize: 14, color: 'var(--fg-secondary)', maxWidth: 540, margin: '10px auto 0' }}>
            Researches the market, runs the numbers, drafts trades on your Alpaca paper account — and shows every tool call along the way.
          </div>
        </div>
      </div>
    </div>

    {/* Command bar */}
    <div style={{ padding: '24px 32px 12px' }}>
      <CommandBar onRun={onRun} />
    </div>

    {/* Prompt grid */}
    <div style={{ padding: '8px 32px 24px' }}>
      <div className="kicker" style={{ marginBottom: 12 }}>Try one of these</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
        {PROMPTS.map((p, i) => (
          <button key={p.id} className="prompt-card" onClick={() => onRun(p)} style={{
            display: 'flex', flexDirection: 'column', gap: 10, padding: 14,
            background: 'var(--bg-surface)', border: '1px solid var(--border)',
            borderRadius: 10, cursor: 'pointer',
            textAlign: 'left', transition: 'border-color 140ms, background 140ms',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                width: 28, height: 28, borderRadius: 7,
                background: 'var(--bull-bg)', border: '1px solid var(--bull-border)',
                color: 'var(--bull-strong)',
              }}>
                <Icon name={p.icon} size={14} />
              </span>
              <span className="prompt-kbd mono" style={{
                fontSize: 10, padding: '2px 6px', borderRadius: 4,
                border: '1px solid var(--border)', color: 'var(--fg-tertiary)',
              }}>{i + 1}</span>
            </div>
            <div style={{ fontSize: 13.5, lineHeight: 1.45, color: 'var(--fg-primary)' }}>{p.text}</div>
          </button>
        ))}
      </div>
    </div>

    {/* Market vitals strip */}
    <div style={{
      marginTop: 'auto',
      padding: '14px 32px',
      borderTop: '1px solid var(--border)',
      display: 'flex', gap: 28, alignItems: 'center',
      background: 'var(--bg-surface)',
    }}>
      <div className="micro" style={{ color: 'var(--fg-tertiary)' }}>MARKET PULSE</div>
      <Vital label="REGIME" value="RISK-ON" tone="bull" />
      <Vital label="VIX" value="14.28" delta="−0.42" tone="bull" />
      <Vital label="BREADTH" value="68%" sub="adv/decl" tone="bull" />
      <Vital label="F&G" value="68 · GREED" tone="warn" />
      <div style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 8 }}>
        <div className="wave" aria-hidden>
          <span style={{ height: 4 }} /><span style={{ height: 8 }} /><span style={{ height: 11 }} /><span style={{ height: 6 }} /><span style={{ height: 9 }} />
        </div>
        <span className="micro" style={{ color: 'var(--bull-strong)' }}>STREAMS LIVE · 14 SOURCES</span>
      </div>
    </div>
  </div>;
}

function Vital({ label, value, delta, sub, tone }) {
  const c = tone === 'bull' ? 'var(--bull-strong)' : tone === 'bear' ? 'var(--bear-strong)' : tone === 'warn' ? 'var(--gold)' : 'var(--fg-primary)';
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
    <span className="micro" style={{ fontSize: 9.5, color: 'var(--fg-tertiary)' }}>{label}</span>
    <span style={{ display: 'inline-flex', gap: 6, alignItems: 'baseline' }}>
      <span className="mono" style={{ fontSize: 13, color: c }}>{value}</span>
      {delta && <span className="mono" style={{ fontSize: 11, color: c }}>{delta}</span>}
      {sub && <span className="micro" style={{ fontSize: 9.5 }}>{sub}</span>}
    </span>
  </div>;
}

/* === Phase pipeline ============================================== */
const PHASES = [
  { id: 0, label: 'INTENT',   icon: 'message-square' },
  { id: 1, label: 'CONTEXT',  icon: 'database' },
  { id: 2, label: 'RESEARCH', icon: 'search' },
  { id: 3, label: 'SIZING',   icon: 'sliders-horizontal' },
  { id: 4, label: 'PROPOSE',  icon: 'check-circle-2' },
];

function Pipeline({ activePhase, done }) {
  return <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
    {PHASES.map((p, i) => (
      <React.Fragment key={p.id}>
        <div className={'phase ' + (activePhase >= p.id ? 'phase-active' : '')} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, minWidth: 84 }}>
          <div className="phase-node" style={{
            width: 36, height: 36, borderRadius: 10,
            border: '1px solid ' + (activePhase >= p.id ? 'var(--bull-border)' : 'var(--border)'),
            background: activePhase >= p.id ? 'var(--bull-bg)' : 'var(--bg-surface)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            color: activePhase >= p.id ? 'var(--bull-strong)' : 'var(--fg-tertiary)',
            transition: 'all 220ms cubic-bezier(0.22,1,0.36,1)',
            position: 'relative', overflow: 'hidden',
          }}>
            {activePhase === p.id && !done && (
              <span style={{
                position: 'absolute', inset: 0,
                background: 'linear-gradient(90deg, transparent, rgba(74,222,128,0.6), transparent)',
                animation: 'sweep 1.6s linear infinite',
              }} />
            )}
            <Icon name={activePhase > p.id || done ? 'check' : p.icon} size={16} />
          </div>
          <span className="phase-label micro" style={{
            color: activePhase >= p.id ? 'var(--bull-strong)' : 'var(--fg-tertiary)',
            fontSize: 10,
          }}>{p.label}</span>
        </div>
        {i < PHASES.length - 1 && (
          <div className={'conn ' + (activePhase > p.id ? 'done' : '')} />
        )}
      </React.Fragment>
    ))}
  </div>;
}

/* === Running log ================================================ */
function LogStream({ events }) {
  const scroller = useRef(null);
  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [events.length]);

  const phaseLabel = ['intent', 'context', 'research', 'sizing', 'propose'];
  const kindColor = (k) => ({
    sys:  'var(--fg-tertiary)',
    task: 'var(--fg-primary)',
    tool: 'var(--bull-strong)',
    ok:   'var(--bull-strong)',
    note: 'var(--gold)',
  }[k] || 'var(--fg-primary)');

  return <div ref={scroller} className="log-scroll" style={{
    fontFamily: 'var(--font-mono)', fontSize: 12.5, lineHeight: 1.6,
    color: 'var(--fg-secondary)',
    background: 'var(--bg-canvas)',
    border: '1px solid var(--border)',
    borderRadius: 10, padding: 14,
    height: 320, overflowY: 'auto',
  }}>
    {events.map((e, i) => {
      const ts = String(Math.floor(e.at_ms / 1000)).padStart(2, '0') + '.' + String(e.at_ms % 1000).padStart(3, '0');
      return <div key={i} className="log-row" style={{ display: 'grid', gridTemplateColumns: '64px 92px 1fr', columnGap: 14, marginBottom: 4 }}>
        <span style={{ color: 'var(--fg-quaternary)' }}>{ts}</span>
        <span style={{ color: 'var(--fg-tertiary)' }}>[{phaseLabel[e.phase]}]</span>
        <span style={{ color: kindColor(e.kind), whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {e.kind === 'task' && '↳ '}{e.kind === 'tool' && '· '}{e.kind === 'ok' && '✓ '}{e.kind === 'note' && '› '}
          {e.text}
          {e.sub && <span style={{ display: 'block', color: 'var(--fg-tertiary)', paddingLeft: 14, fontSize: 11.5 }}>{e.sub}</span>}
        </span>
      </div>;
    })}
    {events.length > 0 && events[events.length-1].kind !== 'ok' && <span className="caret" style={{ background: 'var(--bull-strong)' }} />}
  </div>;
}

/* === Live mini chart that draws in =============================== */
function LiveChart({ ticker, price, target, stop, action }) {
  // Generate semi-realistic walk ending at last price
  const pts = useMemo(() => {
    let rng = 1;
    const seed = ticker.split('').reduce((a,c) => a + c.charCodeAt(0), 0);
    const r = () => { rng = (rng * 9301 + 49297 + seed) % 233280; return rng / 233280; };
    const arr = [];
    let v = price * 0.93;
    for (let i = 0; i < 80; i++) {
      v += (r() - 0.46) * price * 0.012;
      arr.push(v);
    }
    arr[arr.length - 1] = price;
    return arr;
  }, [ticker, price]);

  const w = 560, h = 200;
  const min = Math.min(...pts, stop || pts[0]) * 0.995;
  const max = Math.max(...pts, target || pts[0]) * 1.005;
  const span = max - min;
  const x = (i) => (i / (pts.length - 1)) * (w - 40) + 30;
  const y = (v) => h - 30 - ((v - min) / span) * (h - 60);

  const path = pts.map((v, i) => (i === 0 ? 'M' : 'L') + x(i) + ',' + y(v)).join(' ');
  const area = path + ' L' + x(pts.length - 1) + ',' + (h - 30) + ' L' + x(0) + ',' + (h - 30) + ' Z';

  const pos = action === 'BUY';
  const tone = pos ? 'var(--bull-strong)' : 'var(--bear-strong)';

  return <div style={{
    background: 'var(--bg-canvas)', border: '1px solid var(--border)',
    borderRadius: 10, padding: 14,
    display: 'flex', flexDirection: 'column', gap: 8,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span className="mono" style={{ fontSize: 16, fontWeight: 600, letterSpacing: '0.04em' }}>{ticker}</span>
        <span className="micro" style={{ color: 'var(--fg-tertiary)' }}>1D · 5m bars</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <span className="mono" style={{ fontSize: 18, fontWeight: 600 }}>${price.toFixed(2)}</span>
        <span className="mono" style={{ fontSize: 12, color: tone }}>{pos ? '▲ +1.24%' : '▼ −0.86%'}</span>
      </div>
    </div>
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: '100%', height: 200, display: 'block' }}>
      <defs>
        <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={tone} stopOpacity="0.28" />
          <stop offset="100%" stopColor={tone} stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* gridlines */}
      {[0, 0.25, 0.5, 0.75, 1].map(f => (
        <line key={f} x1="30" x2={w-10} y1={30 + f*(h-60)} y2={30 + f*(h-60)} stroke="var(--border-subtle)" strokeWidth="1" strokeDasharray="2 3" />
      ))}
      {/* target line */}
      {target && <g>
        <line x1="30" x2={w-10} y1={y(target)} y2={y(target)} stroke="var(--bull-strong)" strokeWidth="1" strokeDasharray="4 4" opacity="0.55" />
        <text x={w-12} y={y(target)-4} fontSize="10" fontFamily="var(--font-mono)" fill="var(--bull-strong)" textAnchor="end">TARGET ${target.toFixed(2)}</text>
      </g>}
      {/* stop line */}
      {stop && <g>
        <line x1="30" x2={w-10} y1={y(stop)} y2={y(stop)} stroke="var(--bear-strong)" strokeWidth="1" strokeDasharray="4 4" opacity="0.5" />
        <text x={w-12} y={y(stop)-4} fontSize="10" fontFamily="var(--font-mono)" fill="var(--bear-strong)" textAnchor="end">STOP ${stop.toFixed(2)}</text>
      </g>}
      {/* area fill */}
      <path d={area} fill="url(#g1)" className="chart-path" style={{ animation: 'draw 1800ms cubic-bezier(0.22,1,0.36,1) 200ms forwards' }} />
      {/* line */}
      <path d={path} fill="none" stroke={tone} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="chart-path" />
      {/* end dot */}
      <circle cx={x(pts.length-1)} cy={y(pts[pts.length-1])} r="3.5" fill={tone}>
        <animate attributeName="r" values="3.5;5.5;3.5" dur="2s" repeatCount="indefinite" />
      </circle>
    </svg>
  </div>;
}

/* === Trade proposal card ========================================= */
function ProposalCard({ prompt, onApprove, onReject, onAmend }) {
  const pos = prompt.action === 'BUY';
  const tone = prompt.action === 'BUY' ? 'var(--bull-strong)' : prompt.action === 'SELL' ? 'var(--bear-strong)' : 'var(--gold)';
  const toneBg = prompt.action === 'BUY' ? 'var(--bull-bg)' : prompt.action === 'SELL' ? 'var(--bear-bg)' : 'var(--gold-bg)';
  const toneBorder = prompt.action === 'BUY' ? 'var(--bull-border)' : prompt.action === 'SELL' ? 'var(--bear-border)' : 'var(--gold-border)';

  const notional = prompt.qty * prompt.price;
  const reward = prompt.target ? ((prompt.target - prompt.price) / prompt.price * 100) : null;
  const risk = prompt.stop ? ((prompt.price - prompt.stop) / prompt.price * 100) : null;
  const rr = (reward && risk) ? (reward / risk) : null;

  return <div className="slide-up" style={{
    background: 'var(--bg-surface)', border: '1px solid var(--border-strong)',
    borderRadius: 12, overflow: 'hidden',
  }}>
    <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 7,
        padding: '4px 10px', borderRadius: 99,
        background: toneBg, color: tone, border: '1px solid ' + toneBorder,
        fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.1em',
      }}>
        <Icon name="sparkles" size={11} /> PROPOSAL · {prompt.action}
      </span>
      <span className="micro" style={{ color: 'var(--fg-tertiary)' }}>run #2843 · 3.7s · 6 tools</span>
      <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <Icon name="shield-check" size={12} color="var(--fg-tertiary)" />
        <span className="micro" style={{ color: 'var(--fg-tertiary)' }}>PAPER · NOT ADVICE</span>
      </span>
    </div>

    <div style={{ padding: '20px 18px 18px', display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 24 }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 6 }}>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em' }}>
            {prompt.action} <span style={{ color: tone }}>{prompt.qty}</span> {prompt.ticker}
          </span>
          <span className="mono" style={{ fontSize: 14, color: 'var(--fg-secondary)' }}>@ market</span>
        </div>
        <div style={{ fontSize: 13.5, color: 'var(--fg-secondary)', lineHeight: 1.55, maxWidth: 460 }}>
          {prompt.rationale}
        </div>

        {/* Confidence bar */}
        <div style={{ marginTop: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span className="micro" style={{ color: 'var(--fg-tertiary)' }}>CONFIDENCE</span>
            <span className="mono" style={{ fontSize: 12, color: 'var(--bull-strong)' }}>{prompt.confidence}%</span>
          </div>
          <div style={{ height: 4, borderRadius: 99, background: 'var(--bg-surface-2)', overflow: 'hidden' }}>
            <div className="conf-fill" style={{
              height: '100%', width: prompt.confidence + '%',
              background: 'linear-gradient(90deg, var(--bull), var(--bull-strong))',
              boxShadow: '0 0 12px rgba(74,222,128,0.55)',
            }} />
          </div>
        </div>
      </div>

      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1,
        background: 'var(--border)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden',
      }}>
        {[
          { l: 'NOTIONAL', v: '$' + notional.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
          { l: 'LIMIT', v: '$' + prompt.price.toFixed(2) },
          { l: 'STOP', v: prompt.stop ? '$' + prompt.stop.toFixed(2) : '—', tone: prompt.stop ? 'var(--bear-strong)' : 'var(--fg-tertiary)' },
          { l: 'TARGET', v: prompt.target ? '$' + prompt.target.toFixed(2) : '—', tone: prompt.target ? 'var(--bull-strong)' : 'var(--fg-tertiary)' },
          { l: 'RISK %', v: risk ? '−' + risk.toFixed(2) + '%' : '—', tone: 'var(--bear-strong)' },
          { l: 'REWARD %', v: reward ? '+' + reward.toFixed(2) + '%' : '—', tone: 'var(--bull-strong)' },
          { l: 'R / R', v: rr ? rr.toFixed(2) + '×' : '—' },
          { l: 'HORIZON', v: '5–21d' },
        ].map(s => (
          <div key={s.l} style={{ background: 'var(--bg-surface)', padding: '10px 12px' }}>
            <div className="micro" style={{ color: 'var(--fg-tertiary)', fontSize: 9.5 }}>{s.l}</div>
            <div className="mono" style={{ fontSize: 13, color: s.tone || 'var(--fg-primary)', marginTop: 2 }}>{s.v}</div>
          </div>
        ))}
      </div>
    </div>

    <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
      <button onClick={onApprove} style={{
        display: 'inline-flex', alignItems: 'center', gap: 7, padding: '9px 16px',
        background: 'var(--bull)', color: '#0C0B09', border: 0, borderRadius: 8,
        fontSize: 12.5, fontWeight: 600, letterSpacing: '0.04em', cursor: 'pointer',
        boxShadow: '0 0 24px rgba(34,197,94,0.25)',
      }}>
        <Icon name="check" size={12} /> APPROVE & PLACE
      </button>
      <button onClick={onAmend} style={{
        display: 'inline-flex', alignItems: 'center', gap: 7, padding: '9px 14px',
        background: 'transparent', color: 'var(--fg-primary)',
        border: '1px solid var(--border-strong)', borderRadius: 8,
        fontSize: 12.5, fontWeight: 500, cursor: 'pointer',
      }}>
        <Icon name="pencil" size={12} /> Amend
      </button>
      <button onClick={onReject} style={{
        display: 'inline-flex', alignItems: 'center', gap: 7, padding: '9px 14px',
        background: 'transparent', color: 'var(--bear-strong)',
        border: '1px solid var(--bear-border)', borderRadius: 8,
        fontSize: 12.5, fontWeight: 500, cursor: 'pointer',
      }}>
        <Icon name="x" size={12} /> Discard
      </button>
      <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--fg-tertiary)' }}>
        Approval expires in <span className="mono" style={{ color: 'var(--fg-secondary)' }}>04:48</span>
      </span>
    </div>
  </div>;
}

/* === Running state =============================================== */
function RunningCanvas({ prompt, onDone, onAbort }) {
  const [events, setEvents] = useState([]);
  const [activePhase, setActivePhase] = useState(0);
  const [done, setDone] = useState(false);
  const script = useMemo(() => buildScript(prompt), [prompt.id]);
  const timers = useRef([]);

  useEffect(() => {
    setEvents([]); setActivePhase(0); setDone(false);
    timers.current.forEach(clearTimeout);
    timers.current = [];

    script.forEach((ev) => {
      const tm = setTimeout(() => {
        setEvents(prev => [...prev, ev]);
        setActivePhase(p => Math.max(p, ev.phase));
      }, ev.at_ms);
      timers.current.push(tm);
    });

    const last = script[script.length - 1].at_ms + 400;
    timers.current.push(setTimeout(() => setDone(true), last));

    return () => timers.current.forEach(clearTimeout);
  }, [prompt.id]);

  const elapsed = events.length > 0 ? (events[events.length - 1].at_ms / 1000).toFixed(2) : '0.00';
  const toolsUsed = events.filter(e => e.kind === 'tool' || e.kind === 'task').length;

  return <div style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: 24 }}>
    {/* Header strip with the prompt + abort */}
    <div style={{
      display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px',
      background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 12,
    }}>
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 32, height: 32, borderRadius: 8,
        background: 'var(--bull-bg)', border: '1px solid var(--bull-border)', color: 'var(--bull-strong)',
      }}>
        <Icon name="plane" size={15} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="micro" style={{ color: 'var(--fg-tertiary)', marginBottom: 2 }}>RUN #2843 · {done ? 'COMPLETE' : 'IN PROGRESS'}</div>
        <div style={{ fontSize: 14, color: 'var(--fg-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          “{prompt.text}”
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--fg-secondary)' }}>
        <span>⏱ {elapsed}s</span>
        <span style={{ width: 1, height: 14, background: 'var(--border)' }} />
        <span>⚙ {toolsUsed} tools</span>
        <span style={{ width: 1, height: 14, background: 'var(--border)' }} />
        <span>$ 0.0014</span>
      </div>
      <button onClick={onAbort} style={{
        display: 'inline-flex', alignItems: 'center', gap: 7, padding: '7px 12px',
        background: 'transparent', color: done ? 'var(--fg-secondary)' : 'var(--bear-strong)',
        border: '1px solid ' + (done ? 'var(--border)' : 'var(--bear-border)'),
        borderRadius: 8, fontSize: 11.5, cursor: 'pointer',
      }}>
        <Icon name={done ? 'rotate-ccw' : 'square'} size={11} /> {done ? 'NEW RUN' : 'ABORT'}
      </button>
    </div>

    {/* Pipeline */}
    <div style={{
      padding: '20px 24px', background: 'var(--bg-surface)',
      border: '1px solid var(--border)', borderRadius: 12,
    }}>
      <Pipeline activePhase={activePhase} done={done} />
    </div>

    {/* Two columns: log + chart */}
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div className="kicker" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="live-dot" /> LIVE REASONING
        </div>
        <LogStream events={events} />
        <ToolChips events={events} />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div className="kicker" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="line-chart" size={11} /> SIGNAL VIEW · {prompt.ticker}
        </div>
        {activePhase >= 2 && <LiveChart ticker={prompt.ticker} price={prompt.price} target={prompt.target} stop={prompt.stop} action={prompt.action} />}
        {activePhase < 2 && <div style={{
          height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'var(--bg-canvas)', border: '1px dashed var(--border)', borderRadius: 10,
          color: 'var(--fg-tertiary)', fontSize: 12,
        }}>Waiting for research phase…</div>}
        {activePhase >= 2 && <SignalRack ticker={prompt.ticker} />}
      </div>
    </div>

    {/* Proposal */}
    {done && <ProposalCard prompt={prompt} onApprove={onDone} onAmend={onDone} onReject={onAbort} />}
  </div>;
}

/* Tool chip rack derived from events */
function ToolChips({ events }) {
  const tools = events.filter(e => e.kind === 'tool' || e.kind === 'task');
  if (tools.length === 0) return null;
  return <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
    {tools.map((t, i) => (
      <span key={i} className="tool-chip mono" style={{
        fontSize: 10.5, padding: '3px 8px', borderRadius: 4,
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        color: t.kind === 'tool' ? 'var(--bull-strong)' : 'var(--fg-secondary)',
        letterSpacing: '0.02em',
      }}>
        {t.kind === 'tool' ? '⚙ ' : '↳ '}{t.text}
      </span>
    ))}
  </div>;
}

/* Signal rack: 4 indicator pills */
function SignalRack({ ticker }) {
  const sigs = [
    { name: 'RSI(14)', val: '62.4', tone: 'bull', sub: 'momentum' },
    { name: 'MACD',    val: 'BULL CROSS', tone: 'bull', sub: 'trend' },
    { name: 'EMA 20',  val: 'ABOVE', tone: 'bull', sub: '+1.2σ' },
    { name: 'BREADTH', val: '68%', tone: 'bull', sub: 'sector' },
  ];
  return <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
    {sigs.map(s => (
      <div key={s.name} className="slide-up" style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
        background: 'var(--bg-canvas)', border: '1px solid var(--border)', borderRadius: 8,
      }}>
        <span className="mono" style={{ fontSize: 11, color: 'var(--fg-tertiary)' }}>{s.name}</span>
        <span style={{ flex: 1 }} />
        <span className="mono" style={{ fontSize: 12, color: s.tone === 'bull' ? 'var(--bull-strong)' : 'var(--bear-strong)' }}>{s.val}</span>
        <span className="micro" style={{ fontSize: 9.5, color: 'var(--fg-tertiary)' }}>{s.sub}</span>
      </div>
    ))}
  </div>;
}

/* === Right column ================================================ */
function PaperAccount({ running }) {
  const [equity, setEquity] = useState(100479.47);
  // Subtle live tick while running
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setEquity(e => e + (Math.random() - 0.5) * 4.2), 1800);
    return () => clearInterval(id);
  }, [running]);
  return <div style={{
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: 12, overflow: 'hidden',
  }}>
    <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid var(--border)' }}>
      <Icon name="wallet" size={14} color="var(--bull-strong)" />
      <span className="micro" style={{ color: 'var(--fg-secondary)', letterSpacing: '0.12em', fontSize: 11 }}>PAPER ACCOUNT</span>
      <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span className="live-dot" />
        <span className="micro" style={{ fontSize: 9.5 }}>SYNCED · ALPACA</span>
      </span>
    </div>
    <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, background: 'var(--border)', margin: 0 }}>
      {[
        { l: 'EQUITY',    v: '$' + equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }), tone: 'var(--fg-primary)' },
        { l: 'CASH',      v: '$90,520.19' },
        { l: 'UNREALIZED', v: '+$480.86', sub: '+5.07%', tone: 'var(--bull-strong)' },
        { l: 'DAY P&L',   v: '$0.00', sub: 'paper', tone: 'var(--fg-tertiary)' },
      ].map((s, i) => (
        <div key={i} style={{ background: 'var(--bg-surface)', padding: '14px 14px' }}>
          <div className="micro" style={{ color: 'var(--fg-tertiary)', fontSize: 9.5, marginBottom: 4 }}>{s.l}</div>
          <div className="mono" style={{ fontSize: 17, fontWeight: 600, color: s.tone || 'var(--fg-primary)' }}>{s.v}</div>
          {s.sub && <div className="mono" style={{ fontSize: 11, color: s.tone || 'var(--fg-tertiary)', marginTop: 2 }}>{s.sub}</div>}
        </div>
      ))}
    </div>
    <div style={{ padding: '14px 16px', borderTop: '1px solid var(--border)' }}>
      <div className="micro" style={{ color: 'var(--fg-tertiary)', marginBottom: 10 }}>POSITIONS · 2</div>
      {[
        { sym: 'AAPL', qty: 5, px: 279.96, pnl: +144.30 },
        { sym: 'AMD',  qty: 18, px: 448.81, pnl: +336.56 },
      ].map(p => (
        <div key={p.sym} style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', alignItems: 'baseline', gap: 12, padding: '8px 0', borderTop: '1px solid var(--border-subtle)' }}>
          <span>
            <span className="mono" style={{ fontSize: 13, fontWeight: 600, color: 'var(--bull-strong)' }}>{p.sym}</span>
            <span className="mono" style={{ fontSize: 11, color: 'var(--fg-tertiary)', marginLeft: 8 }}>{p.qty} @ ${p.px.toFixed(2)}</span>
          </span>
          <span className="mono" style={{ fontSize: 12, color: 'var(--bull-strong)' }}>↗ +${p.pnl.toFixed(2)}</span>
        </div>
      ))}
    </div>
  </div>;
}

function Capabilities() {
  const items = [
    { icon: 'trending-up',    t: 'Research · Buy · Sell · Hedge · Rebalance' },
    { icon: 'database',       t: 'Reads your live account before every action' },
    { icon: 'cpu',            t: 'Python sandbox for sizing & risk math' },
    { icon: 'shield-check',   t: 'Paper trading only — no real money moves' },
    { icon: 'eye',            t: 'Every tool call logged to your audit trail' },
  ];
  return <div style={{
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: 12, padding: 16,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
      <Icon name="sparkles" size={14} color="var(--bull-strong)" />
      <span className="micro" style={{ color: 'var(--fg-secondary)', letterSpacing: '0.12em', fontSize: 11 }}>CAPABILITIES</span>
    </div>
    {items.map((it, i) => (
      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0' }}>
        <Icon name={it.icon} size={14} color="var(--bull-strong)" />
        <span style={{ fontSize: 12.5, color: 'var(--fg-secondary)' }}>{it.t}</span>
      </div>
    ))}
  </div>;
}

/* Recent runs (lightweight) */
function RecentRuns() {
  const runs = [
    { t: '2m ago',  txt: 'Hedge SPY for next week earnings season',     ok: 'EXECUTED', tone: 'bull' },
    { t: '14m ago', txt: 'Find 3 oversold mid-caps with insider buying', ok: 'PROPOSED', tone: 'warn' },
    { t: '42m ago', txt: 'Daily portfolio briefing',                     ok: 'READ',     tone: 'mute' },
    { t: '1h ago',  txt: 'Trim positions up >12% MTD',                   ok: 'AMENDED',  tone: 'warn' },
  ];
  const tones = { bull: 'var(--bull-strong)', warn: 'var(--gold)', mute: 'var(--fg-tertiary)' };
  return <div style={{
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: 12, padding: 16,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
      <Icon name="history" size={13} color="var(--fg-tertiary)" />
      <span className="micro" style={{ color: 'var(--fg-secondary)', letterSpacing: '0.12em', fontSize: 11 }}>RECENT RUNS</span>
      <span style={{ marginLeft: 'auto', fontSize: 10.5, color: 'var(--fg-tertiary)' }}>view all →</span>
    </div>
    {runs.map((r, i) => (
      <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '10px 0', borderTop: i === 0 ? '0' : '1px solid var(--border-subtle)' }}>
        <span className="mono" style={{ fontSize: 10.5, color: 'var(--fg-quaternary)', marginTop: 2, minWidth: 56 }}>{r.t}</span>
        <span style={{ flex: 1, fontSize: 12.5, color: 'var(--fg-secondary)', lineHeight: 1.45 }}>{r.txt}</span>
        <span className="mono" style={{ fontSize: 9.5, padding: '2px 6px', borderRadius: 4, background: 'var(--bg-canvas)', color: tones[r.tone] || 'var(--fg-tertiary)', border: '1px solid var(--border)', letterSpacing: '0.08em' }}>{r.ok}</span>
      </div>
    ))}
  </div>;
}

Object.assign(window, { IdleCanvas, RunningCanvas, PaperAccount, Capabilities, RecentRuns });
