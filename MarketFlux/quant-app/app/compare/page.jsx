import Link from "next/link";

import { PageHero, Panel, Shell } from "@/components/shell";
import { competitorContent } from "@/lib/content";

export default function CompareHubPage() {
  return (
    <Shell active="/compare">
      <PageHero
        eyebrow="Compare Hub"
        title="Compare MarketFlux against the tools investors already know."
        summary="These pages should help serious evaluators decide whether they need a dashboard, a transcript database, an AI chatbot, or a true research operating system."
        actions={[
          { href: "/vs/finchat", label: "Start with FinChat" },
          { href: "/alternatives/bloomberg-terminal", label: "Bloomberg alternative", kind: "ghost" },
        ]}
      />

      <div className="grid-2">
        {Object.entries(competitorContent).map(([slug, competitor]) => (
          <Panel key={slug} title={competitor.name} eyebrow="Comparison page">
            <p className="hero-copy">{competitor.audience}</p>
            <p>{competitor.marketFluxEdge}</p>
            <Link href={slug === "bloomberg-terminal" ? "/alternatives/bloomberg-terminal" : `/vs/${slug}`} className="ghost-link">
              Open page
            </Link>
          </Panel>
        ))}
      </div>
    </Shell>
  );
}

