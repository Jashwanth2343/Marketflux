import { notFound } from "next/navigation";

import { BulletStack, PageHero, Panel, Shell } from "@/components/shell";
import { competitorContent } from "@/lib/content";

export function generateStaticParams() {
  return Object.keys(competitorContent)
    .filter((slug) => slug !== "bloomberg-terminal")
    .map((slug) => ({ slug }));
}

export default async function CompetitorPage({ params }) {
  const { slug } = await params;
  const competitor = competitorContent[slug];
  if (!competitor) {
    notFound();
  }

  return (
    <Shell active="/compare">
      <PageHero
        eyebrow="Competitor Comparison"
        title={`MarketFlux vs ${competitor.name}`}
        summary={competitor.marketFluxEdge}
        actions={[
          { href: "/compare", label: "Back To Compare Hub" },
          { href: "/briefing", label: "Open Product", kind: "ghost" },
        ]}
      />

      <div className="grid-2">
        <Panel title={`${competitor.name} strengths`} eyebrow="Be honest">
          <BulletStack items={competitor.strengths} />
        </Panel>
        <Panel title={`${competitor.name} limits`} eyebrow="Where MarketFlux differs">
          <BulletStack items={competitor.weaknesses} />
        </Panel>
      </div>

      <div className="grid-2">
        <Panel title={`${competitor.name} is best for`} eyebrow="Use case">
          <p className="hero-copy">{competitor.bestFor}</p>
        </Panel>
        <Panel title="Why choose MarketFlux" eyebrow="MarketFlux edge">
          <p className="hero-copy">{competitor.marketFluxEdge}</p>
        </Panel>
      </div>
    </Shell>
  );
}
