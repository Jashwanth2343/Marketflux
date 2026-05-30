/* MarketFlux · Trading Copilot · app orchestrator */

function App() {
  const [tab, setTab] = useState('agent');
  const [running, setRunning] = useState(null); // prompt object or null

  return <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
    <TopNav />
    <TickerTape />
    <PageHeader tab={tab} setTab={setTab} />

    <main data-screen-label="01 Copilot Agent" style={{ maxWidth: 1480, margin: '0 auto', width: '100%', padding: '20px 32px 64px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 360px', gap: 20, alignItems: 'start' }}>
        {/* LEFT — canvas */}
        <section style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderRadius: 14,
          minHeight: 720,
          overflow: 'hidden',
          position: 'relative',
        }}>
          {/* Persistent canvas header */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '14px 18px', borderBottom: '1px solid var(--border)',
            background: 'rgba(15,18,22,0.4)',
          }}>
            <span style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 32, height: 32, borderRadius: 8,
              background: 'var(--bull-bg)', border: '1px solid var(--bull-border)',
              color: 'var(--bull-strong)',
            }}>
              <Icon name="plane" size={15} />
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 14, letterSpacing: '-0.01em' }}>
                Copilot Agent <span style={{ color: 'var(--bull-strong)', marginLeft: 4 }}>●</span>
              </span>
              <span className="micro" style={{ color: 'var(--fg-tertiary)' }}>AUTONOMOUS · PAPER · v1.4</span>
            </div>
            <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
              <button style={{
                display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px',
                background: 'transparent', color: 'var(--fg-secondary)',
                border: '1px solid var(--border)', borderRadius: 6, fontSize: 11, cursor: 'pointer',
              }}>
                <Icon name="settings" size={11} /> Settings
              </button>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px',
                background: 'var(--bg-surface-2)', border: '1px solid var(--border)',
                borderRadius: 6, fontFamily: 'var(--font-mono)', fontSize: 10.5,
                letterSpacing: '0.08em', color: 'var(--fg-tertiary)',
              }}>
                <Icon name="shield-alert" size={11} /> NOT ADVICE
              </span>
            </span>
          </div>

          {running ? (
            <RunningCanvas prompt={running} onDone={() => setRunning(null)} onAbort={() => setRunning(null)} />
          ) : (
            <IdleCanvas onRun={(p) => setRunning(p)} />
          )}
        </section>

        {/* RIGHT — sidecar */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: 16, position: 'sticky', top: 100 }}>
          <PaperAccount running={!!running} />
          <RecentRuns />
          <Capabilities />
        </aside>
      </div>
    </main>

    {/* Footer attribution */}
    <footer style={{
      padding: '20px 32px', borderTop: '1px solid var(--border)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      fontSize: 11, color: 'var(--fg-tertiary)',
    }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
        <Icon name="activity" size={12} color="var(--bull-strong)" />
        MarketFlux Copilot · v1.4.2 · build 2843
      </span>
      <span>Paper trading only · Not investment advice · Data via Polygon & Alpaca</span>
    </footer>
  </div>;
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
