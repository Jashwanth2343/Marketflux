import Link from "next/link";

const appNav = [
  { href: "/briefing", label: "Briefing" },
  { href: "/research/NVDA", label: "Research" },
  { href: "/signals", label: "Signals" },
  { href: "/watchlists", label: "Watchlists" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/methodology", label: "Methodology" },
];

const siteNav = [
  { href: "/", label: "Home" },
  { href: "/product", label: "Product" },
  { href: "/pricing", label: "Pricing" },
  { href: "/compare", label: "Compare" },
];

export function Shell({ active, children }) {
  return (
    <div className="shell-root">
      <header className="topbar">
        <div className="brand-lockup">
          <Link href="/" className="brand-mark">
            MARKETFLUX
          </Link>
          <span className="brand-tag">AI-native quant research OS</span>
        </div>
        <nav className="nav-row nav-site">
          {siteNav.map((item) => (
            <Link key={item.href} href={item.href} className={active === item.href ? "nav-link active" : "nav-link"}>
              {item.label}
            </Link>
          ))}
        </nav>
        <nav className="nav-row nav-app">
          {appNav.map((item) => (
            <Link key={item.href} href={item.href} className={active === item.href ? "nav-link active" : "nav-link"}>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="topbar-actions">
          <Link href="/briefing" className="primary-link">
            Generate Brief
          </Link>
        </div>
      </header>
      <main className="page-frame">{children}</main>
      <footer className="footer">
        <div>Research only. No trade execution. Evidence first.</div>
        <div>Built for serious self-directed investors.</div>
      </footer>
    </div>
  );
}

export function PageHero({ eyebrow, title, summary, actions = [] }) {
  return (
    <section className="hero-card">
      <div className="eyebrow">{eyebrow}</div>
      <div className="hero-headline-row">
        <h1>{title}</h1>
      </div>
      <p className="hero-copy">{summary}</p>
      {actions.length > 0 && (
        <div className="action-row">
          {actions.map((action) => (
            <Link key={action.href} href={action.href} className={action.kind === "ghost" ? "ghost-link" : "primary-link"}>
              {action.label}
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

export function Panel({ title, eyebrow, children, aside }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
          <h2>{title}</h2>
        </div>
        {aside ? <div className="panel-aside">{aside}</div> : null}
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}

export function MetricGrid({ items }) {
  return (
    <div className="metric-grid">
      {items.map((item) => (
        <div key={item.label} className="metric-card">
          <div className="metric-label">{item.label}</div>
          <div className="metric-value">{item.value}</div>
          {item.note ? <div className="metric-note">{item.note}</div> : null}
        </div>
      ))}
    </div>
  );
}

export function SimpleTable({ columns, rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row[columns[0]] || index}`}>
              {columns.map((column) => (
                <td key={column}>{row[column]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CitationList({ citations = [] }) {
  if (!citations.length) {
    return <p className="muted-copy">No citations were returned for this block yet.</p>;
  }
  return (
    <ul className="citation-list">
      {citations.map((citation) => (
        <li key={`${citation.label}-${citation.source}`}>
          <strong>{citation.label}</strong>
          <span>{citation.source}</span>
        </li>
      ))}
    </ul>
  );
}

export function BulletStack({ items = [] }) {
  if (!items.length) {
    return <p className="muted-copy">No items yet.</p>;
  }
  return (
    <ul className="bullet-stack">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

