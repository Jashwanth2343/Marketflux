/* ===================================================================
   MarketFlux UI Kit — agents.jsx
   ===================================================================
   The Agents surface. Modelled on Public.com's agentic brokerage page:
   prompt → status → category tags. Same MarketFlux brand language.
   =================================================================== */

const statusColors = {
  active:        { label: 'Active',      color: 'var(--bull-strong)', bg: 'var(--bull-bg)',  border: 'var(--bull-border)', dot: true },
  paused:        { label: 'Paused',      color: 'var(--gold)',        bg: 'var(--gold-bg)',  border: 'var(--gold-border)', dot: false },
  draft:         { label: 'Draft',       color: 'var(--fg-secondary)', bg: 'var(--bg-surface-2)', border: 'var(--border)', dot: false },
  'coming-soon': { label: 'Coming soon', color: 'var(--fg-tertiary)', bg: 'var(--bg-surface-2)', border: 'var(--border)', dot: false },
};

function AgentStatusPill({ status }) {
  const s = statusColors[status] || statusColors.draft;
  return <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '3px 9px', borderRadius: 9999,
    fontSize: 11, fontWeight: 500,
    background: s.bg, color: s.color, border: '1px solid ' + s.border,
  }}>
    {s.dot && <span style={{
      width: 6, height: 6, borderRadius: 9999,
      background: s.color, boxShadow: '0 0 6px ' + s.color,
    }} />}
    {s.label}
  </span>;
}

function AgentTag({ children }) {
  return <span style={{
    fontSize: 11, color: 'var(--fg-secondary)',
    padding: '2px 8px', borderRadius: 9999,
    background: 'var(--bg-surface-2)', border: '1px solid var(--border)',
    whiteSpace: 'nowrap',
  }}>{children}</span>;
}

function AgentCard({ agent, onOpen }) {
  return <div onClick={() => onOpen && onOpen(agent)} style={{
    background: 'var(--bg-surface)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    padding: 18,
    display: 'flex', flexDirection: 'column', gap: 12,
    cursor: 'pointer',
    transition: 'border-color var(--duration-fast) var(--ease-out), transform var(--duration-fast) var(--ease-out)',
  }}
  onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent-border)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.transform = 'none'; }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span style={{
        fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 500,
        letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--fg-tertiary)',
      }}>Agent</span>
      <AgentStatusPill status={agent.status} />
    </div>
    <div>
      <div style={{
        fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 19,
        letterSpacing: '-0.01em', color: 'var(--fg-primary)', marginBottom: 6,
      }}>{agent.title}</div>
      <div style={{ fontSize: 13.5, color: 'var(--fg-secondary)', lineHeight: 1.55 }}>
        {agent.prompt}
      </div>
    </div>
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 'auto' }}>
      {agent.tags.map(t => <AgentTag key={t}>{t}</AgentTag>)}
    </div>
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      paddingTop: 10, borderTop: '1px solid var(--border)',
      fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-tertiary)',
      fontVariantNumeric: 'tabular-nums',
    }}>
      <span>{agent.runs} runs</span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--accent-strong)' }}>
        Open workspace <Icon name="arrow-right" size={12} style={{ color: 'currentColor' }} />
      </span>
    </div>
  </div>;
}

/* -------- Agents surface ---------------------------------------- */
function Agents() {
  const [prompt, setPrompt] = useState(window.MF_AGENT_PROMPTS[0]);
  const [promptIdx, setPromptIdx] = useState(0);
  const [selected, setSelected] = useState(null);

  function cycle(delta) {
    const next = (promptIdx + delta + window.MF_AGENT_PROMPTS.length) % window.MF_AGENT_PROMPTS.length;
    setPromptIdx(next);
    setPrompt(window.MF_AGENT_PROMPTS[next]);
  }

  if (selected) return <AgentDetail agent={selected} onBack={() => setSelected(null)} />;

  return <div style={{ padding: '32px 24px 64px', display: 'flex', flexDirection: 'column', gap: 56 }}>

    {/* === HERO ============================================ */}
    <section style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 1080, margin: '0 auto', width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ width: 6, height: 6, borderRadius: 9999, background: 'var(--accent)', boxShadow: '0 0 6px var(--accent-glow)' }} />
        <span style={{ fontSize: 12, color: 'var(--accent-strong)', fontWeight: 500, letterSpacing: '0.04em' }}>FluxAI Agents · now in beta</span>
      </div>

      <h1 style={{
        margin: 0,
        fontFamily: 'var(--font-display)', fontWeight: 700,
        fontSize: 'clamp(40px, 6vw, 64px)', letterSpacing: '-0.025em',
        lineHeight: 1.02, color: 'var(--fg-primary)',
      }}>
        Agents.<br />
        <span style={{ color: 'var(--fg-secondary)' }}>For your portfolio.</span>
      </h1>

      <p style={{
        margin: 0, maxWidth: 620,
        fontSize: 17, lineHeight: 1.55, color: 'var(--fg-secondary)',
      }}>
        For the first time, you can build agents that monitor the market, automate your cash workflows, and execute your trades — described in plain English, running 24/7 inside MarketFlux.
      </p>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button variant="primary">Request access</Button>
        <Button variant="ghost" icon="play">Watch the demo</Button>
      </div>

      {/* Hero prompt frame */}
      <div style={{
        marginTop: 12,
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        padding: 24,
        display: 'grid',
        gridTemplateColumns: '1fr 320px',
        gap: 28, alignItems: 'center',
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--fg-tertiary)', fontSize: 12 }}>
            <span style={{ display: 'inline-flex', gap: 4 }}>
              {window.MF_AGENT_PROMPTS.map((_, i) => (
                <span key={i} style={{
                  width: i === promptIdx ? 18 : 6, height: 6, borderRadius: 9999,
                  background: i === promptIdx ? 'var(--accent-strong)' : 'var(--border-strong)',
                  transition: 'all 220ms var(--ease-out)',
                }} />
              ))}
            </span>
            <span>Example prompt {String(promptIdx + 1).padStart(2, '0')} of {String(window.MF_AGENT_PROMPTS.length).padStart(2, '0')}</span>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
              <a onClick={() => cycle(-1)} style={{ cursor: 'pointer', padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)' }}>←</a>
              <a onClick={() => cycle(+1)} style={{ cursor: 'pointer', padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)' }}>→</a>
            </span>
          </div>
          <div style={{
            fontFamily: 'var(--font-serif)',
            fontSize: 'clamp(22px, 2.4vw, 30px)',
            lineHeight: 1.25, color: 'var(--fg-primary)',
            letterSpacing: '-0.01em',
          }}>
            “{prompt}”
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <Button variant="primary" icon="sparkles">Build this agent</Button>
            <Button variant="secondary">Customise</Button>
          </div>
        </div>
        {/* Right: mock agent workflow */}
        <div style={{
          background: 'var(--bg-canvas)',
          border: '1px solid var(--border)',
          borderRadius: 10, padding: 16,
          display: 'flex', flexDirection: 'column', gap: 10,
        }}>
          {[
            { step: '01', label: 'Monitor VIX every minute', state: 'active' },
            { step: '02', label: 'Wait for VIX > 25', state: 'pending' },
            { step: '03', label: 'Buy SPY 30-day put · $1,000', state: 'pending' },
            { step: '04', label: 'Notify on fill', state: 'pending' },
          ].map(s => (
            <div key={s.step} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 10,
                color: 'var(--fg-tertiary)', minWidth: 22,
              }}>{s.step}</span>
              <span style={{
                width: 8, height: 8, borderRadius: 9999,
                background: s.state === 'active' ? 'var(--accent)' : 'var(--border-strong)',
                boxShadow: s.state === 'active' ? '0 0 6px var(--accent-glow)' : 'none',
                flexShrink: 0,
              }} />
              <span style={{ fontSize: 12.5, color: s.state === 'active' ? 'var(--fg-primary)' : 'var(--fg-secondary)' }}>{s.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>

    {/* === HOW IT WORKS ===================================== */}
    <section style={{ maxWidth: 1080, margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column', gap: 28 }}>
      <div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--fg-tertiary)', marginBottom: 8 }}>How it works</div>
        <h2 style={{ margin: 0, fontSize: 32, fontWeight: 600, letterSpacing: '-0.02em' }}>
          Describe what you want.<br />
          <span style={{ color: 'var(--fg-secondary)' }}>Your agent handles the rest.</span>
        </h2>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {[
          { icon: 'message-square', n: '01', t: 'Start with a prompt',
            d: 'Instead of manually monitoring the markets and entering trades, describe your intent in plain English.' },
          { icon: 'sparkles', n: '02', t: 'Refine the strategy',
            d: 'FluxAI translates your intent into a workflow you can review, edit, and approve before it ever runs.' },
          { icon: 'zap', n: '03', t: 'Activate your agent',
            d: 'Once active, it monitors market conditions and only executes when your criteria are met. Stop or edit anytime.' },
        ].map(card => (
          <div key={card.n} style={{
            background: 'var(--bg-surface)', border: '1px solid var(--border)',
            borderRadius: 12, padding: 22, display: 'flex', flexDirection: 'column', gap: 12,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{
                width: 38, height: 38, borderRadius: 10,
                background: 'var(--accent-bg)', border: '1px solid var(--accent-border)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-strong)',
              }}>
                <Icon name={card.icon} size={18} />
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-tertiary)' }}>{card.n}</span>
            </div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 17 }}>{card.t}</div>
            <div style={{ fontSize: 13.5, color: 'var(--fg-secondary)', lineHeight: 1.55 }}>{card.d}</div>
          </div>
        ))}
      </div>
    </section>

    {/* === AGENT GRID ====================================== */}
    <section style={{ maxWidth: 1080, margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--fg-tertiary)', marginBottom: 8 }}>Agents on MarketFlux</div>
          <h2 style={{ margin: 0, fontSize: 32, fontWeight: 600, letterSpacing: '-0.02em' }}>
            Agents can do a lot. <span style={{ color: 'var(--fg-secondary)' }}>Here's a start.</span>
          </h2>
        </div>
        <Button variant="secondary" icon="plus">New agent</Button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {window.MF_AGENTS.map(a => <AgentCard key={a.id} agent={a} onOpen={setSelected} />)}
      </div>
    </section>

    {/* === CAPABILITIES =================================== */}
    <section style={{ maxWidth: 1080, margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--fg-tertiary)', marginBottom: 8 }}>Agent skills</div>
        <h2 style={{ margin: 0, fontSize: 32, fontWeight: 600, letterSpacing: '-0.02em' }}>
          Trading, indicators, data, cash. <span style={{ color: 'var(--fg-secondary)' }}>One framework.</span>
        </h2>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
        {window.MF_AGENT_CAPABILITIES.map(cap => (
          <div key={cap.title} style={{
            background: 'var(--bg-surface)', border: '1px solid var(--border)',
            borderRadius: 12, padding: 22, display: 'flex', flexDirection: 'column', gap: 14,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 8,
                background: 'var(--bg-surface-2)', border: '1px solid var(--border)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon name={cap.icon} size={17} style={{ color: 'var(--accent-strong)' }} />
              </div>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 17 }}>{cap.title}</div>
            </div>
            <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
              {cap.items.map(it => (
                <li key={it} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13.5, color: 'var(--fg-secondary)' }}>
                  <span style={{ color: 'var(--accent-strong)', flexShrink: 0 }}>✓</span>
                  {it}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>

    {/* === SAFETY ========================================== */}
    <section style={{ maxWidth: 1080, margin: '0 auto', width: '100%' }}>
      <div style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        padding: 32,
        display: 'grid', gridTemplateColumns: '320px 1fr', gap: 36, alignItems: 'center',
      }}>
        <div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--fg-tertiary)', marginBottom: 8 }}>Safety first</div>
          <h2 style={{ margin: 0, fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em' }}>
            You are in <span style={{ color: 'var(--accent-strong)' }}>complete control</span>. Always.
          </h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 18 }}>
          {[
            { i: 'eye',    t: 'Transparency', d: 'Every action is visible in your activity feed. No black box.' },
            { i: 'lock',   t: 'Security',     d: 'Agents run inside your authenticated brokerage. No third-party API keys.' },
            { i: 'shield', t: 'Control',      d: 'You approve every agent before it goes live. Edit, pause or stop anytime.' },
          ].map(c => (
            <div key={c.t} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <Icon name={c.i} size={20} style={{ color: 'var(--accent-strong)' }} />
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 15 }}>{c.t}</div>
              <div style={{ fontSize: 13, color: 'var(--fg-secondary)', lineHeight: 1.55 }}>{c.d}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  </div>;
}

Object.assign(window, { Agents, AgentCard, AgentStatusPill, AgentTag });
