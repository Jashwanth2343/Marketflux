import { CitationList, MetricGrid, PageHero, Panel, Shell, SimpleTable } from "@/components/shell";
import { getPortfolioDiagnostics } from "@/lib/api";

export default async function PortfolioPage() {
  const diagnostics = await getPortfolioDiagnostics();
  const rows = (diagnostics.holdings || []).map((holding) => ({
    ticker: holding.ticker,
    sector: holding.sector,
    shares: holding.shares,
    price: holding.price,
    value: holding.value,
    change_percent: holding.change_percent,
  }));

  return (
    <Shell active="/portfolio">
      <PageHero
        eyebrow="Portfolio Diagnostics"
        title="Make the portfolio research-aware, not just performance-aware."
        summary="This page is about concentration, macro sensitivity, thesis coverage, and overlap. It should feel like portfolio review, not just position bookkeeping."
        actions={[
          { href: "/watchlists", label: "Open Watchlists" },
          { href: "/research/QQQ", label: "Research Proxy Name", kind: "ghost" },
        ]}
      />

      <MetricGrid
        items={[
          { label: "Total Value", value: diagnostics.total_value, note: diagnostics.as_of },
          { label: "Concentration", value: diagnostics.concentration_risk, note: "Top-weight lens" },
          { label: "Macro Sensitivity", value: diagnostics.macro_sensitivity, note: "Growth vs defensive proxy" },
        ]}
      />

      <div className="grid-2">
        <Panel title="Sector exposure" eyebrow="What the book is actually exposed to">
          <SimpleTable columns={["sector", "weight"]} rows={diagnostics.sector_exposure || []} />
        </Panel>
        <Panel title="Research guidance" eyebrow="Next actions">
          <ul className="bullet-stack">
            {(diagnostics.insights || []).map((insight) => (
              <li key={insight}>{insight}</li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel title="Holdings" eyebrow="Backend-driven">
        <SimpleTable columns={["ticker", "sector", "shares", "price", "value", "change_percent"]} rows={rows} />
      </Panel>

      <Panel title="Citations" eyebrow="Evidence">
        <CitationList citations={diagnostics.citations || []} />
      </Panel>
    </Shell>
  );
}

