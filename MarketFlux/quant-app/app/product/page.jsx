import Link from "next/link";

import { PageHero, Panel, Shell } from "@/components/shell";
import { featureContent } from "@/lib/content";

export default function ProductPage() {
  return (
    <Shell active="/product">
      <PageHero
        eyebrow="Product Surface"
        title="A public quant research workflow, not a generic market dashboard."
        summary="The product is built around briefing, signals, research workspaces, watchlists, and portfolio overlays. Chat is embedded as a copilot, not the primary interface."
        actions={[
          { href: "/briefing", label: "Open App" },
          { href: "/compare", label: "See Compare Hub", kind: "ghost" },
        ]}
      />

      <div className="grid-2">
        {Object.entries(featureContent).map(([slug, feature]) => (
          <Panel key={slug} title={feature.title} eyebrow="Feature">
            <p className="hero-copy">{feature.summary}</p>
            <ul className="bullet-stack">
              {feature.bullets.map((bullet) => (
                <li key={bullet}>{bullet}</li>
              ))}
            </ul>
            <Link href={`/features/${slug}`} className="ghost-link">
              Read more
            </Link>
          </Panel>
        ))}
      </div>
    </Shell>
  );
}

