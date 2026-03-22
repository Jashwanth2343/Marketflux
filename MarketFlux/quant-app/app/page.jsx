import Link from "next/link";

import { PageHero, Panel, Shell } from "@/components/shell";
import { competitorContent, featureContent, productPillars } from "@/lib/content";

export default function HomePage() {
  return (
    <Shell active="/">
      <PageHero
        eyebrow="Public Quant Research"
        title="Build the public-facing research desk that hedge funds keep private."
        summary="MarketFlux vNext is an AI-native quant research operating system for serious retail investors. The product is research-only by design: no broker routing, no execution theater, and no opaque answers without evidence."
        actions={[
          { href: "/briefing", label: "Open Morning Brief" },
          { href: "/product", label: "See Product Surfaces", kind: "ghost" },
        ]}
      />

      <div className="grid-3">
        {productPillars.map((pillar) => (
          <Panel key={pillar.title} title={pillar.title} eyebrow={pillar.eyebrow}>
            <p className="hero-copy">{pillar.summary}</p>
          </Panel>
        ))}
      </div>

      <div className="grid-2">
        <Panel title="Flagship workflows" eyebrow="Month 1">
          <div className="tag-row">
            <span className="tag">Morning Brief</span>
            <span className="tag">Signals Feed</span>
            <span className="tag">Ticker Research Workspace</span>
            <span className="tag">Watchlist Board</span>
            <span className="tag">Portfolio Diagnostics</span>
          </div>
        </Panel>
        <Panel title="Guardrails" eyebrow="Non-negotiable">
          <ul className="bullet-stack">
            <li>Research only. No trade execution in v1.</li>
            <li>Every output should carry freshness, confidence, and citations.</li>
            <li>Signal detection must be systematic before it becomes narrative.</li>
          </ul>
        </Panel>
      </div>

      <Panel title="Feature architecture" eyebrow="Product">
        <div className="grid-3">
          {Object.entries(featureContent).map(([slug, feature]) => (
            <div key={slug} className="signal-card">
              <div className="kicker">{feature.title}</div>
              <div>{feature.summary}</div>
              <Link href={`/features/${slug}`} className="ghost-link">
                Open feature page
              </Link>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Competitive framing" eyebrow="Compare">
        <div className="grid-2">
          {Object.entries(competitorContent)
            .filter(([slug]) => slug !== "bloomberg-terminal")
            .map(([slug, competitor]) => (
              <div key={slug} className="signal-card">
                <div className="kicker">{competitor.name}</div>
                <div>{competitor.marketFluxEdge}</div>
                <Link href={`/vs/${slug}`} className="ghost-link">
                  Read the comparison
                </Link>
              </div>
            ))}
        </div>
      </Panel>
    </Shell>
  );
}

