/* ===================================================================
   MarketFlux UI Kit — components.jsx
   ===================================================================
   Atoms and molecules. Every component is small and cosmetic — these
   are not production implementations. They demonstrate visual coverage.
   =================================================================== */

const { useState, useEffect, useRef, useMemo } = React;

/* -------- Icon: thin wrapper around Lucide UMD ---------------------- */
function Icon({ name, size = 16, className = '', style = {} }) {
  const ref = useRef(null);
  useEffect(() => {
    if (window.lucide && ref.current) {
      ref.current.innerHTML = '';
      const el = document.createElement('i');
      el.setAttribute('data-lucide', name);
      ref.current.appendChild(el);
      window.lucide.createIcons({ attrs: { width: size, height: size } });
    }
  }, [name, size]);
  return <span ref={ref} className={className}
    style={{ display: 'inline-flex', width: size, height: size, ...style }} />;
}

/* -------- Kicker (small muted label) ----------------------- */
function Kicker({ children, color, style }) {
  return <div style={{
    fontFamily: 'var(--font-body)',
    fontSize: 12,
    fontWeight: 500,
    color: color || 'var(--fg-secondary)',
    ...style,
  }}>{children}</div>;
}

/* -------- LiveDot --------------------------------------------------- */
function LiveDot({ color = 'var(--bull-strong)' }) {
  return <span className="mf-live-dot" style={{ background: color }} />;
}

/* -------- Card ------------------------------------------------------ */
const cardStyles = {
  base: {
    background: 'var(--bg-surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-2)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px',
    borderBottom: '1px solid var(--border)',
    gap: 8,
  },
  body: { padding: 16, flex: 1, minHeight: 0 },
};
function Card({ children, hero, style }) {
  return <div style={{ ...cardStyles.base, ...(style||{}) }}>
    {children}
  </div>;
}
function CardHeader({ title, icon, iconColor, right, kicker }) {
  return <div style={cardStyles.header}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
      {icon && <Icon name={icon} size={14} style={{ color: iconColor || 'var(--fg-secondary)' }} />}
      <span style={{
        fontFamily: 'var(--font-display)',
        fontSize: 14,
        fontWeight: 600,
        letterSpacing: '-0.01em',
        color: 'var(--fg-primary)',
        whiteSpace: 'nowrap',
      }}>{title}</span>
      {kicker}
    </div>
    {right && <div style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--fg-tertiary)' }}>{right}</div>}
  </div>;
}
function CardBody({ children, style }) {
  return <div style={{ ...cardStyles.body, ...(style||{}) }}>{children}</div>;
}

/* -------- Button ---------------------------------------------------- */
const btnBase = {
  fontFamily: 'var(--font-body)',
  fontSize: 13,
  fontWeight: 600,
  padding: '9px 16px',
  borderRadius: 10,
  border: '1px solid',
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  lineHeight: 1,
  whiteSpace: 'nowrap',
  transition: 'background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out), border-color var(--duration-fast) var(--ease-out)',
};
const btnVariants = {
  primary:     { background: 'var(--accent)',       color: 'var(--accent-fg)',  borderColor: 'var(--accent)' },
  secondary:   { background: 'transparent',         color: 'var(--fg-primary)', borderColor: 'var(--border-strong)' },
  ghost:       { background: 'transparent',         color: 'var(--fg-secondary)', borderColor: 'transparent' },
  destructive: { background: 'transparent',         color: 'var(--bear)',       borderColor: 'var(--bear-border)' },
  agent:       { background: 'var(--accent-bg)',    color: 'var(--accent-strong)',borderColor: 'var(--accent-border)' },
};
function Button({ variant = 'primary', icon, children, onClick, style }) {
  return <button onClick={onClick} style={{ ...btnBase, ...btnVariants[variant], ...(style||{}) }}>
    {icon && <Icon name={icon} size={12} />}
    {children}
  </button>;
}

/* -------- Badge ----------------------------------------------------- */
const badgeBase = {
  fontFamily: 'var(--font-body)',
  fontSize: 11,
  fontWeight: 500,
  letterSpacing: '0.02em',
  padding: '3px 9px',
  border: '1px solid',
  borderRadius: 'var(--radius-1)',
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  lineHeight: 1.4,
};
const badgeVariants = {
  bull:    { color: 'var(--bull-strong)',  background: 'var(--bull-bg)',  borderColor: 'var(--bull-border)' },
  bear:    { color: 'var(--bear-strong)',  background: 'var(--bear-bg)',  borderColor: 'var(--bear-border)' },
  warn:    { color: 'var(--neutral-strong)', background: 'var(--neutral-bg)', borderColor: 'var(--neutral-border)' },
  neutral: { color: 'var(--neutral-strong)', background: 'var(--neutral-bg)', borderColor: 'var(--neutral-border)' },
  cyan:    { color: 'var(--fg-secondary)', background: 'var(--bg-surface-2)', borderColor: 'var(--border)' },
  agent:   { color: 'var(--accent-strong)', background: 'var(--accent-bg)', borderColor: 'var(--accent-border)' },
};
function Badge({ variant = 'neutral', children, dot }) {
  const v = badgeVariants[variant] || badgeVariants.neutral;
  return <span style={{ ...badgeBase, ...v }}>
    {dot && <span style={{ width: 6, height: 6, borderRadius: 9999, background: v.color, display: 'inline-block' }} />}
    {children}
  </span>;
}

/* -------- Delta — paired arrow + colour --------------------------- */
function Delta({ value, pct, size = 'm' }) {
  const pos = (pct ?? value) >= 0;
  const color = pos ? 'var(--bull-strong)' : 'var(--bear-strong)';
  const f = size === 'l' ? 14 : size === 's' ? 11 : 13;
  const sign = pos ? '+' : '−';
  const num = Math.abs(value ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const p = pct == null ? null : Math.abs(pct).toFixed(2);
  return <span style={{
    color, fontFamily: 'var(--font-mono)', fontSize: f, fontWeight: 600,
    fontVariantNumeric: 'tabular-nums', display: 'inline-flex', alignItems: 'baseline', gap: 4,
  }}>
    <span style={{ fontSize: f - 2 }}>{pos ? '▲' : '▼'}</span>
    {value != null && <span>{sign}{num}</span>}
    {p != null && <span>({sign}{p}%)</span>}
  </span>;
}

function Pct({ value, size = 's', withArrow = true }) {
  const pos = value >= 0;
  const color = pos ? 'var(--bull-strong)' : 'var(--bear-strong)';
  const f = size === 'l' ? 14 : size === 's' ? 11 : 13;
  const sign = pos ? '+' : '−';
  return <span style={{
    color, fontFamily: 'var(--font-mono)', fontSize: f, fontWeight: 600,
    fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
  }}>
    {withArrow && (pos ? '▲ ' : '▼ ')}{sign}{Math.abs(value).toFixed(2)}%
  </span>;
}

/* -------- Sparkline ------------------------------------------------- */
function Sparkline({ pts, color = 'var(--bull)', height = 24, width = 120, dashed = false }) {
  const min = Math.min(...pts), max = Math.max(...pts);
  const span = max - min || 1;
  const step = width / (pts.length - 1);
  const path = pts.map((v, i) => `${i * step},${height - ((v - min) / span) * (height - 2) - 1}`).join(' ');
  return <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none">
    <polyline fill="none" stroke={color} strokeWidth="1.4"
      strokeDasharray={dashed ? '3 2' : 'none'} points={path} />
  </svg>;
}

Object.assign(window, {
  Icon, Kicker, LiveDot, Card, CardHeader, CardBody,
  Button, Badge, Delta, Pct, Sparkline,
});
