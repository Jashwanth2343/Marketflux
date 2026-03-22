import { CitationList, MetricGrid, PageHero, Panel, Shell } from "@/components/shell";
import { getBriefing } from "@/lib/api";

export default async function BriefingPage() {
  const briefing = await getBriefing();
  const macro = briefing.macro_regime || {};
  const signals = briefing.top_signals || [];
  const watchlist = briefing.watchlist_updates || [];
  const keyIndicators = (macro.key_indicators || []).map((item) => ({
    label: item.name,
    value: item.value ?? "N/A",
    note: item.signal,
  }));

  return (
    <Shell active="/briefing">
      <PageHero
        eyebrow="Morning Brief"
        title={`${(macro.regime || "transitional").replace(/_/g, " ")} market framing for today`}
        summary={macro.summary || "Open the day with a quantified view of regime, risk, and watchlist priorities."}
        actions={[
          { href: "/signals", label: "Open Signals" },
          { href: "/research/NVDA", label: "Run Deep Dive", kind: "ghost" },
        ]}
      />

      <div className="grid-2">
        <Panel title="Macro regime" eyebrow={`Confidence ${macro.confidence || 0} / 100`}>
          <MetricGrid items={keyIndicators} />
        </Panel>
        <Panel title="Model lane" eyebrow="Cost-aware routing">
          <MetricGrid
            items={[
              {
                label: "Tier",
                value: briefing.methodology?.model_lane?.tier ?? "0",
                note: "Lower tiers stay deterministic and cheap.",
              },
              {
                label: "Lane",
                value: briefing.methodology?.model_lane?.lane ?? "research graph",
                note: "Narrative should never outrun evidence.",
              },
            ]}
          />
        </Panel>
      </div>

      <Panel title="Top signals" eyebrow="Ranked by relevance">
        <div className="grid-2">
          {signals.map((signal) => (
            <div key={`${signal.signal_type}-${signal.title}`} className="signal-card">
              <div className="signal-meta">
                <div className="kicker">{signal.signal_type.replace(/_/g, " ")}</div>
                <div className="signal-severity">{signal.severity}</div>
              </div>
              <h3>{signal.title}</h3>
              <div>{signal.summary}</div>
              <div className="tag-row">
                {(signal.tickers || []).map((ticker) => (
                  <span key={ticker} className="tag">
                    {ticker}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <div className="grid-2">
        <Panel title="Watchlist board" eyebrow="What matters today">
          <div className="grid-2">
            {watchlist.length ? (
              watchlist.map((item) => (
                <div key={item.ticker} className="signal-card">
                  <div className="signal-meta">
                    <div className="kicker">{item.ticker}</div>
                    <div className="signal-severity">{item.priority || "normal"}</div>
                  </div>
                  <h3>{item.name || item.ticker}</h3>
                  <div>{item.next_step}</div>
                  <div className="tag-row">
                    {(item.tags || []).map((tag) => (
                      <span key={tag} className="tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ))
            ) : (
              <p className="muted-copy">No watchlist data yet. The board will populate as soon as holdings and watchlists are connected.</p>
            )}
          </div>
        </Panel>
        <Panel title="Citations" eyebrow="Evidence">
          <CitationList citations={briefing.citations || []} />
        </Panel>
      </div>
    </Shell>
  );
}

