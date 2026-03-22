import { notFound } from "next/navigation";

import { BulletStack, PageHero, Panel, Shell } from "@/components/shell";
import { featureContent } from "@/lib/content";

export function generateStaticParams() {
  return Object.keys(featureContent).map((slug) => ({ slug }));
}

export default async function FeatureDetailPage({ params }) {
  const { slug } = await params;
  const feature = featureContent[slug];
  if (!feature) {
    notFound();
  }

  return (
    <Shell active="/product">
      <PageHero
        eyebrow="Feature Detail"
        title={feature.title}
        summary={feature.summary}
        actions={[
          { href: "/product", label: "Back To Product" },
          { href: "/briefing", label: "Open Product", kind: "ghost" },
        ]}
      />
      <Panel title="Why it matters" eyebrow="Design intent">
        <BulletStack items={feature.bullets} />
      </Panel>
    </Shell>
  );
}
