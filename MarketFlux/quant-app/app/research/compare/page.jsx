import { PageHero, Panel, Shell, SimpleTable } from "@/components/shell";
import { getCompare } from "@/lib/api";

export default async function ResearchComparePage() {
  const compare = await getCompare(["AAPL", "MSFT", "NVDA"]);
  const rows = (compare.rows || []).map((row) => ({
    ticker: row.ticker,
    name: row.name,
    sector: row.sector,
    price: row.price,
    pe_ratio: row.pe_ratio,
    revenue_growth: row.revenue_growth,
    recommendation_key: row.recommendation_key,
  }));

  return (
    <Shell active="/research/NVDA">
      <PageHero
        eyebrow="Research Compare"
        title="Compare companies inside a single institutional-style workspace."
        summary="The compare flow should behave like a research desk shortcut, not a generic screener table."
        actions={[
          { href: "/signals", label: "Open Signals" },
          { href: "/compare", label: "Public Compare Hub", kind: "ghost" },
        ]}
      />
      <Panel title="Comparison grid" eyebrow={compare.as_of || "Live"}>
        <SimpleTable
          columns={["ticker", "name", "sector", "price", "pe_ratio", "revenue_growth", "recommendation_key"]}
          rows={rows}
        />
      </Panel>
    </Shell>
  );
}

