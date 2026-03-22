import { CitationList, PageHero, Panel, Shell } from "@/components/shell";
import { getWatchlistBoard } from "@/lib/api";

export default async function WatchlistsPage() {
  const board = await getWatchlistBoard();

  return (
    <Shell active="/watchlists">
      <PageHero
        eyebrow="Watchlist Board"
        title="Turn saved tickers into an actual research book."
        summary="Watchlists should track catalysts, saved theses, and what changed today, instead of acting as a passive ticker bucket."
        actions={[
          { href: "/briefing", label: "Back To Briefing" },
          { href: "/research/NVDA", label: "Open Workspace", kind: "ghost" },
        ]}
      />

      <div className="grid-2">
        <Panel title="Tracked names" eyebrow={board.watchlist_id || "public"}>
          <div className="grid-2">
            {(board.items || []).map((item) => (
              <div key={item.ticker} className="signal-card">
                <div className="signal-meta">
                  <div className="kicker">{item.ticker}</div>
                  <div className="signal-severity">{item.priority}</div>
                </div>
                <h3>{item.name || item.ticker}</h3>
                <div>{item.latest_headline || "No fresh headline returned."}</div>
                <div>{item.next_step}</div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Saved theses" eyebrow="Research memory">
          {(board.saved_theses || []).length ? (
            <div className="grid-2">
              {board.saved_theses.map((thesis, index) => (
                <div key={`${thesis.ticker}-${index}`} className="signal-card">
                  <div className="kicker">{thesis.ticker}</div>
                  <h3>{thesis.stance}</h3>
                  <div>{thesis.thesis_text}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted-copy">No saved theses yet. The backend route is ready for research-memory writes.</p>
          )}
        </Panel>
      </div>

      <Panel title="Evidence" eyebrow={board.as_of || "As of now"}>
        <CitationList citations={board.citations || []} />
      </Panel>
    </Shell>
  );
}

