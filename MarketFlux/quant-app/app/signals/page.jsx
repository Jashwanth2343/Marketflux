import { CitationList, PageHero, Panel, Shell } from "@/components/shell";
import { getSignals } from "@/lib/api";

export default async function SignalsPage() {
  const payload = await getSignals();
  const signals = payload.signals || [];

  return (
    <Shell active="/signals">
      <PageHero
        eyebrow="Signal Feed"
        title="Systematic market signals, ranked before the narrative starts."
        summary="This feed is designed to feel like a public research desk: timestamps, evidence, tickers, and severity all come first."
        actions={[
          { href: "/briefing", label: "Back To Briefing" },
          { href: "/research/NVDA", label: "Open Workspace", kind: "ghost" },
        ]}
      />

      <Panel title="Active signals" eyebrow={payload.as_of || "Live"}>
        <div className="grid-2">
          {signals.map((signal) => (
            <div
              key={`${signal.signal_type}-${signal.title}-${signal.created_at || signal.freshness || "live"}`}
              className="signal-card"
            >
              <div className="signal-meta">
                <div className="kicker">{signal.asset_scope}</div>
                <div className="signal-severity">{signal.severity}</div>
              </div>
              <h3>{signal.title}</h3>
              <div>{signal.summary}</div>
              <div className="metric-note">
                Freshness: {signal.freshness || payload.as_of || "Live"} | Confidence model: deterministic signal engine
              </div>
              {!!(signal.evidence || []).length && (
                <div className="evidence-list">
                  {(signal.evidence || []).map((item) => (
                    <div key={item} className="evidence-item">
                      {item}
                    </div>
                  ))}
                </div>
              )}
              <div className="tag-row">
                {(signal.tickers || []).map((ticker) => (
                  <span key={ticker} className="tag">
                    {ticker}
                  </span>
                ))}
              </div>
              <CitationList citations={signal.citations || []} />
            </div>
          ))}
        </div>
      </Panel>
    </Shell>
  );
}
