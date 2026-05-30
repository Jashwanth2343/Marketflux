/* MarketFlux · Autonomous Core · chrome
   Floating glass panels over the dot-grid canvas. */

const { useState, useEffect, useRef, useMemo } = React;

/* ---------- Lucide icon wrapper ---------- */
function Icon({ name, size = 16, color = 'currentColor', style = {}, stroke = 1.75 }) {
  const ref = useRef(null);
  useEffect(() => {
    if (window.lucide && ref.current) {
      ref.current.innerHTML = '';
      const i = document.createElement('i');
      i.setAttribute('data-lucide', name);
      ref.current.appendChild(i);
      window.lucide.createIcons({ attrs: { width: size, height: size, 'stroke-width': stroke } });
    }
  }, [name, size, stroke]);
  return <span ref={ref} style={{ display: 'inline-flex', width: size, height: size, color, ...style }} />;
}

/* =====================================================================
   TOP BAR — floating, full-width strip with project chip + actions
   ===================================================================== */
function TopBar({ agentName, onMenu, onRun, running }) {
  return <header style={{
    position: 'fixed', top: 16, left: 16, right: 16, zIndex: 50,
    display: 'flex', alignItems: 'center', gap: 14,
    height: 52, padding: '0 10px 0 6px',
  }} className="glass no-select">
    {/* Menu */}
    <button className="btn-icon" onClick={onMenu} aria-label="Menu" style={{ border: 0 }}>
      <Icon name="panel-left" size={16} />
    </button>

    {/* Wordmark + project name */}
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="agent-orb" style={{ width: 22, height: 22, position: 'relative' }}>
          <span style={{
            position: 'absolute', inset: 5, borderRadius: 99,
            background: 'rgba(10,16,6,0.65)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Icon name="activity" size={9} color="#B6FF6B" stroke={2.4} />
          </span>
        </span>
        <span style={{ fontFamily: 'var(--display)', fontWeight: 600, fontSize: 14, letterSpacing: '-0.005em' }}>
          Market<span style={{ background: 'var(--agent-grad)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>Flux</span>
        </span>
      </div>
      <span style={{ width: 1, height: 18, background: 'var(--hairline)' }} />
      <span style={{ fontSize: 13, color: 'var(--fg-secondary)', fontWeight: 500 }}>
        {agentName}
      </span>
      <span style={{
        fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-tertiary)',
        padding: '2px 6px', borderRadius: 4,
        border: '1px solid var(--hairline)', letterSpacing: '0.08em',
      }}>v3.2</span>
    </div>

    {/* Center: live status */}
    <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
      <span className="chip" style={{ cursor: 'default', padding: '5px 11px' }}>
        <span className="pulse-dot" />
        <span className="mono" style={{ fontSize: 10.5, letterSpacing: '0.1em' }}>
          {running ? 'AGENT RUNNING · 14 TOOLS' : 'PAPER · NYSE OPEN · 14:32 ET'}
        </span>
      </span>
    </div>

    {/* Actions */}
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <button className="btn-icon" onClick={onRun} aria-label="Run agent" title="Run agent" style={{
        background: running ? 'transparent' : 'var(--agent-grad)',
        color: running ? 'var(--fg-secondary)' : '#0A1006',
        border: running ? '1px solid var(--hairline)' : '0',
      }}>
        <Icon name={running ? 'square' : 'play'} size={13} stroke={running ? 2 : 2.5} />
      </button>
      <button className="btn">
        <Icon name="log-out" size={13} /> Export
      </button>
      <button className="btn">
        <Icon name="share-2" size={13} /> Share
      </button>
      <div style={{
        width: 32, height: 32, borderRadius: 99,
        background: 'var(--agent-grad)', color: '#0A1006',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 13, fontWeight: 700,
        boxShadow: '0 0 0 2px var(--bg-canvas), 0 0 0 3px rgba(74,222,128,0.35)',
      }}>J</div>
    </div>
  </header>;
}

/* =====================================================================
   LEFT RAIL — collapsible. Agent runs / chat history.
   ===================================================================== */
function LeftRail({ open, onClose, runs, activeId, onSelect }) {
  if (!open) return null;
  return <aside style={{
    position: 'fixed', top: 80, left: 16, bottom: 84, width: 280,
    zIndex: 40, display: 'flex', flexDirection: 'column',
    padding: 12, gap: 10,
  }} className="glass">
    {/* Header */}
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 4px 8px', borderBottom: '1px solid var(--hairline-soft)' }}>
      <Icon name="message-square-text" size={13} color="var(--fg-secondary)" />
      <span className="micro" style={{ color: 'var(--fg-secondary)' }}>AGENT RUNS</span>
      <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--fg-tertiary)', fontFamily: 'var(--font-mono)' }}>{runs.length}</span>
      <button className="btn-icon" onClick={onClose} style={{ width: 22, height: 22, border: 0 }} aria-label="Close rail">
        <Icon name="x" size={12} />
      </button>
    </div>

    {/* New run */}
    <button className="btn" style={{
      justifyContent: 'flex-start', borderStyle: 'dashed',
      borderColor: 'rgba(244,239,227,0.18)', color: 'var(--fg-secondary)',
    }}>
      <Icon name="plus" size={13} /> New agent run
    </button>

    {/* Run list */}
    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
      {runs.map((r, i) => {
        const active = r.id === activeId;
        return <button key={r.id} onClick={() => onSelect(r.id)} style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '9px 10px', borderRadius: 9, border: '1px solid ' + (active ? 'var(--hairline)' : 'transparent'),
          background: active ? 'rgba(244,239,227,0.04)' : 'transparent',
          color: active ? 'var(--fg-primary)' : 'var(--fg-secondary)',
          textAlign: 'left', cursor: 'pointer', fontFamily: 'inherit',
          transition: 'all 140ms ease-out',
        }}
        onMouseEnter={e => !active && (e.currentTarget.style.background = 'rgba(244,239,227,0.025)')}
        onMouseLeave={e => !active && (e.currentTarget.style.background = 'transparent')}>
          {r.status === 'live' ? (
            <span style={{ position: 'relative', width: 16, height: 16, display: 'inline-flex' }}>
              <span className="pulse-dot" style={{ width: 8, height: 8, position: 'absolute', top: 4, left: 4 }} />
            </span>
          ) : (
            <Icon name={r.status === 'ok' ? 'check-circle-2' : 'circle-dashed'} size={13}
              color={r.status === 'ok' ? '#4ADE80' : 'var(--fg-quaternary)'} />
          )}
          <span style={{ flex: 1, fontSize: 12.5, lineHeight: 1.35, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {r.label}
          </span>
          {r.status === 'live' && <span className="micro" style={{ fontSize: 9, color: '#4ADE80' }}>LIVE</span>}
        </button>;
      })}
    </div>

    {/* Footer: agent log toggle */}
    <div style={{ borderTop: '1px solid var(--hairline-soft)', paddingTop: 10, marginTop: 4 }}>
      <button style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 10,
        padding: '9px 10px', borderRadius: 9, border: 0, background: 'transparent',
        color: 'var(--fg-secondary)', fontFamily: 'inherit', cursor: 'pointer', fontSize: 12.5,
      }}>
        <Icon name="terminal" size={13} />
        Agent log
        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--fg-tertiary)', fontFamily: 'var(--font-mono)' }}>342</span>
      </button>
    </div>
  </aside>;
}

/* =====================================================================
   RIGHT TOOL PALETTE — floating column of canvas tools
   ===================================================================== */
function ToolPalette({ tool, setTool }) {
  const tools = [
    { id: 'select', icon: 'mouse-pointer-2', label: 'Select' },
    { id: 'frame',  icon: 'square-dashed',   label: 'Frame' },
    { id: 'draw',   icon: 'pen-line',        label: 'Annotate' },
    { id: 'hand',   icon: 'hand',            label: 'Pan' },
    { id: 'image',  icon: 'image',           label: 'Image' },
    { id: 'palette',icon: 'palette',         label: 'Style' },
    { id: 'star',   icon: 'sparkles',        label: 'AI' },
  ];
  return <aside style={{
    position: 'fixed', top: '50%', right: 16, transform: 'translateY(-50%)',
    zIndex: 40, padding: 6,
    display: 'flex', flexDirection: 'column', gap: 4,
  }} className="glass no-select">
    {tools.map(t => {
      const active = t.id === tool;
      return <button key={t.id} onClick={() => setTool(t.id)} title={t.label}
        style={{
          width: 38, height: 38, borderRadius: 10,
          background: active ? 'rgba(244,239,227,0.08)' : 'transparent',
          border: '1px solid ' + (active ? 'var(--hairline)' : 'transparent'),
          color: active ? 'var(--fg-primary)' : 'var(--fg-secondary)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', transition: 'all 140ms ease-out',
        }}
        onMouseEnter={e => !active && (e.currentTarget.style.background = 'rgba(244,239,227,0.04)')}
        onMouseLeave={e => !active && (e.currentTarget.style.background = 'transparent')}>
        <Icon name={t.icon} size={16} stroke={t.id === 'star' ? 1.8 : 1.6} />
      </button>;
    })}
  </aside>;
}

/* =====================================================================
   BOTTOM PROMPT — chat composer with model picker + suggestion chips
   ===================================================================== */
function BottomPrompt({ onSend, suggestions, model, onModelChange }) {
  const [val, setVal] = useState('');
  const inputRef = useRef(null);
  const handleSubmit = (e) => {
    e.preventDefault();
    if (val.trim()) { onSend(val); setVal(''); }
  };
  return <div style={{
    position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
    zIndex: 45, width: 'min(820px, calc(100vw - 360px))',
    display: 'flex', flexDirection: 'column', gap: 10,
  }} className="no-select">
    {/* Suggestion chips */}
    <div style={{
      display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap',
      paddingBottom: 2,
    }}>
      {suggestions.map((s, i) => (
        <button key={i} className="chip chip-enter" style={{ animationDelay: i * 50 + 'ms' }}
          onClick={() => onSend(s.text)}>
          {s.text}
          {s.num && <span className="chip-num">{s.num}</span>}
        </button>
      ))}
    </div>

    {/* Composer */}
    <form onSubmit={handleSubmit} className="glass-strong"
      style={{
        borderRadius: 18,
        padding: '6px 6px 6px 16px',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
      <button type="button" className="btn-icon" style={{ border: 0, color: 'var(--fg-tertiary)' }} aria-label="Attach">
        <Icon name="plus" size={16} />
      </button>
      <span style={{ color: 'var(--fg-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>/</span>
      <input ref={inputRef} value={val} onChange={e => setVal(e.target.value)}
        placeholder="What would you like the agent to do?"
        style={{
          flex: 1, background: 'transparent', border: 0, outline: 'none',
          color: 'var(--fg-primary)', fontSize: 14.5, fontFamily: 'inherit',
          padding: '8px 0',
        }} />

      {/* Model picker */}
      <ModelPicker value={model} onChange={onModelChange} />

      <button type="button" className="btn-icon" style={{ border: 0, color: 'var(--fg-tertiary)' }} aria-label="Voice">
        <Icon name="mic" size={15} />
      </button>
      <button type="submit" style={{
        width: 36, height: 36, borderRadius: 12,
        background: 'var(--agent-grad)', border: 0,
        color: '#0A1006', cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: '0 0 0 1px rgba(255,255,255,0.06) inset, 0 8px 22px rgba(74,222,128,0.32)',
      }} aria-label="Send">
        <Icon name="arrow-up" size={15} stroke={2.4} />
      </button>
    </form>
  </div>;
}

function ModelPicker({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const models = [
    { id: 'gemini', label: '2.5 Pro',    sub: 'Gemini',    icon: 'sparkle', tone: '#B6FF6B' },
    { id: 'claude', label: 'Sonnet 4.5', sub: 'Claude',    icon: 'sparkle', tone: '#FF9F6B' },
    { id: 'gpt',    label: 'GPT-5',      sub: 'OpenAI',    icon: 'sparkle', tone: '#A8A091' },
  ];
  const current = models.find(m => m.id === value) || models[0];
  return <div style={{ position: 'relative' }}>
    <button type="button" onClick={() => setOpen(o => !o)} style={{
      display: 'inline-flex', alignItems: 'center', gap: 7,
      padding: '6px 10px', borderRadius: 9,
      background: 'rgba(244,239,227,0.04)', border: '1px solid var(--hairline)',
      color: 'var(--fg-secondary)', fontSize: 12, cursor: 'pointer', fontFamily: 'inherit',
    }}>
      <span style={{ width: 7, height: 7, borderRadius: 99, background: current.tone, boxShadow: '0 0 6px ' + current.tone }} />
      {current.label}
      <Icon name="chevron-down" size={11} />
    </button>
    {open && <div className="glass-strong" style={{
      position: 'absolute', bottom: 'calc(100% + 6px)', right: 0,
      width: 220, padding: 4, borderRadius: 12, zIndex: 60,
    }}>
      {models.map(m => (
        <button key={m.id} type="button" onClick={() => { onChange(m.id); setOpen(false); }} style={{
          display: 'flex', alignItems: 'center', gap: 10, width: '100%',
          padding: '8px 10px', borderRadius: 8, border: 0,
          background: value === m.id ? 'rgba(244,239,227,0.05)' : 'transparent',
          color: 'var(--fg-primary)', textAlign: 'left', fontFamily: 'inherit',
          fontSize: 12.5, cursor: 'pointer',
        }}>
          <span style={{ width: 8, height: 8, borderRadius: 99, background: m.tone, boxShadow: '0 0 6px ' + m.tone }} />
          <span style={{ flex: 1 }}>
            <div>{m.label}</div>
            <div style={{ fontSize: 10.5, color: 'var(--fg-tertiary)' }}>{m.sub}</div>
          </span>
          {value === m.id && <Icon name="check" size={13} color="#4ADE80" />}
        </button>
      ))}
    </div>}
  </div>;
}

/* =====================================================================
   AGENT LOG — collapsible footer log indicator (bottom-left)
   ===================================================================== */
function AgentLogFooter({ events, expanded, onToggle }) {
  return <div style={{
    position: 'fixed', left: 16, bottom: 24, zIndex: 45,
    width: expanded ? 320 : 200,
    transition: 'width 220ms ease-out',
  }} className="glass no-select">
    <button onClick={onToggle} style={{
      width: '100%', display: 'flex', alignItems: 'center', gap: 10,
      padding: '10px 14px', background: 'transparent', border: 0,
      color: 'var(--fg-secondary)', fontFamily: 'inherit', cursor: 'pointer', fontSize: 12.5,
      borderRadius: 16,
    }}>
      <Icon name="terminal" size={13} color="#4ADE80" />
      <span>Agent log</span>
      <span style={{
        fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-tertiary)',
        background: 'rgba(244,239,227,0.04)', padding: '2px 6px', borderRadius: 4,
        marginLeft: 'auto',
      }}>{events.length}</span>
      <Icon name={expanded ? 'chevron-down' : 'chevron-up'} size={13} />
    </button>
    {expanded && <div style={{
      maxHeight: 240, overflowY: 'auto', padding: '4px 14px 14px',
      borderTop: '1px solid var(--hairline-soft)',
      fontFamily: 'var(--font-mono)', fontSize: 11, lineHeight: 1.55,
      color: 'var(--fg-secondary)',
    }}>
      {events.slice(-20).map((e, i) => (
        <div key={i} className="log-row" style={{ display: 'flex', gap: 8, padding: '2px 0' }}>
          <span style={{ color: 'var(--fg-quaternary)', minWidth: 36 }}>{e.t}</span>
          <span style={{ color: e.tone || 'var(--fg-secondary)' }}>{e.txt}</span>
        </div>
      ))}
    </div>}
  </div>;
}

Object.assign(window, { Icon, TopBar, LeftRail, ToolPalette, BottomPrompt, AgentLogFooter });
