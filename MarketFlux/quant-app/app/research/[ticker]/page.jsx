import { BulletStack, CitationList, MetricGrid, PageHero, Panel, Shell, SimpleTable } from "@/components/shell";
import { getWorkspace } from "@/lib/api";

export default async function ResearchWorkspacePage({ params }) {
  const { ticker: rawTicker } = await params;
  const ticker = rawTicker.toUpperCase();
  const workspace = await getWorkspace(ticker);
  const snapshot = workspace.snapshot || {};
  const thesis = workspace.thesis || {};
  const technicals = workspace.technicals || {};

  return (
    <Shell active={`/research/${ticker}`}>
      <PageHero
        eyebrow="Ticker Research Workspace"
        title={`${workspace.ticker || ticker} evidence stack`}
        summary="A single workspace that fuses price, documents, insider activity, transcript highlights, macro regime, and explicit bull-base-bear thinking."
        actions={[
          { href: "/signals", label: "Open Signals" },
          { href: "/watchlists", label: "Add To Watchlist", kind: "ghost" },
        ]}
      />

      <Panel title="Snapshot" eyebrow={workspace.as_of || "As of now"}>
        <MetricGrid
          items={[
            { label: "Price", value: snapshot.price ?? "N/A", note: snapshot.name || ticker },
            { label: "Change", value: snapshot.change_percent ?? "N/A", note: snapshot.sector || "Sector unavailable" },
            { label: "P/E", value: snapshot.pe_ratio ?? "N/A", note: snapshot.industry || "Industry unavailable" },
            { label: "Target Mean", value: snapshot.target_mean_price ?? "N/A", note: snapshot.recommendation_key || "Street view unavailable" },
          ]}
        />
      </Panel>

      <div className="grid-2">
        <Panel title="Bull case" eyebrow={`Confidence ${thesis.confidence || 0} / 100`}>
          <BulletStack items={thesis.bull_case || []} />
        </Panel>
        <Panel title="Bear case" eyebrow={thesis.stance || "balanced"}>
          <BulletStack items={thesis.bear_case || []} />
        </Panel>
      </div>

      <div className="grid-2">
        <Panel title="Base case" eyebrow="Portfolio context">
          <BulletStack items={thesis.base_case || []} />
        </Panel>
        <Panel title="Technicals" eyebrow={technicals.trend || "trend unavailable"}>
          <MetricGrid
            items={[
              { label: "20DMA Spread", value: technicals.price_vs_20dma ?? "N/A", note: "Percent versus 20DMA" },
              { label: "50DMA Spread", value: technicals.price_vs_50dma ?? "N/A", note: "Percent versus 50DMA" },
              { label: "Support", value: technicals.support_zone ?? "N/A", note: "Trailing 20-session floor" },
              { label: "Resistance", value: technicals.resistance_zone ?? "N/A", note: "Trailing 20-session ceiling" },
            ]}
          />
        </Panel>
      </div>

      <div className="grid-2">
        <Panel title="Filing intelligence" eyebrow="Structured document layer">
          <BulletStack items={workspace.filings?.highlights || [workspace.filings?.summary || "No filing highlights yet."]} />
          <SimpleTable
            columns={["period_end", "value", "filed"]}
            rows={(workspace.filings?.annual_revenue || []).map((row) => ({
              period_end: row.period_end,
              value: row.value,
              filed: row.filed,
            }))}
          />
        </Panel>
        <Panel title="Transcript highlights" eyebrow="Management language">
          <BulletStack items={workspace.transcripts?.highlights || [workspace.transcripts?.summary || "Transcript coverage unavailable."]} />
        </Panel>
      </div>

      <div className="grid-2">
        <Panel title="Insider signal" eyebrow={workspace.insider?.signal || "neutral"}>
          <BulletStack items={[workspace.insider?.summary || "No insider summary returned."]} />
        </Panel>
        <Panel title="Open questions" eyebrow="Keep the workflow honest">
          <BulletStack items={workspace.open_questions || []} />
        </Panel>
      </div>

      <Panel title="Evidence ledger" eyebrow={workspace.model_lane?.lane || "retrieval-backed synthesis"}>
        <CitationList citations={workspace.citations || []} />
      </Panel>
    </Shell>
  );
}
