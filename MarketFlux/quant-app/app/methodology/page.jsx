import { BulletStack, PageHero, Panel, Shell } from "@/components/shell";

export default function MethodologyPage() {
  return (
    <Shell active="/methodology">
      <PageHero
        eyebrow="Methodology"
        title="Evidence, freshness, and repeatability are the product."
        summary="MarketFlux should earn trust by showing how signals are built, what sources they depend on, and where the confidence comes from."
        actions={[
          { href: "/product", label: "Product Surfaces" },
          { href: "/pricing", label: "Pricing", kind: "ghost" },
        ]}
      />

      <div className="grid-2">
        <Panel title="Signal construction" eyebrow="Quant layer">
          <BulletStack
            items={[
              "Macro regime is rule-informed before any synthesis layer is applied.",
              "Cross-asset states are built from market proxies, not generic sentiment adjectives.",
              "Single-name research pulls price, filings, transcript, insider, and news evidence into one workspace.",
            ]}
          />
        </Panel>
        <Panel title="Research quality rules" eyebrow="Trust layer">
          <BulletStack
            items={[
              "Every meaningful output should include timestamps, citations, and confidence.",
              "Narrative can summarize evidence, but it should never replace the evidence trail.",
              "Research only. The product is intentionally not pretending to be an execution engine.",
            ]}
          />
        </Panel>
      </div>
    </Shell>
  );
}

