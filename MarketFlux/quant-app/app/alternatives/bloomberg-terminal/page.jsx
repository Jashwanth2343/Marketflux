import { BulletStack, PageHero, Panel, Shell } from "@/components/shell";
import { competitorContent } from "@/lib/content";

export default function BloombergAlternativePage() {
  const competitor = competitorContent["bloomberg-terminal"];

  return (
    <Shell active="/compare">
      <PageHero
        eyebrow="Alternative Page"
        title="A Bloomberg Terminal alternative for serious self-directed investors"
        summary="MarketFlux is not trying to clone institutional infrastructure. The product aim is narrower and more public: hedge-fund-style research workflows without the hedge-fund software budget."
        actions={[
          { href: "/compare", label: "Back To Compare Hub" },
          { href: "/briefing", label: "Open Product", kind: "ghost" },
        ]}
      />

      <div className="grid-2">
        <Panel title="Why people look for alternatives" eyebrow="Context">
          <BulletStack
            items={[
              "They want rigorous research workflows without institutional seat costs.",
              "They care more about signals, filings, and watchlists than chat windows and execution terminals.",
              "They need public-market accessibility, not enterprise procurement.",
            ]}
          />
        </Panel>
        <Panel title="Why MarketFlux is different" eyebrow="Positioning">
          <p className="hero-copy">{competitor.marketFluxEdge}</p>
        </Panel>
      </div>

      <Panel title="Bloomberg strengths to respect" eyebrow="Honesty builds trust">
        <BulletStack items={competitor.strengths} />
      </Panel>
    </Shell>
  );
}
