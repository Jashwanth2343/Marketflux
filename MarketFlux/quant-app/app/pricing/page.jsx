import { PageHero, Panel, Shell } from "@/components/shell";
import { pricingTiers } from "@/lib/content";

export default function PricingPage() {
  return (
    <Shell active="/pricing">
      <PageHero
        eyebrow="Pricing"
        title="Institutional research ambition, public-market pricing."
        summary="The pricing posture should reinforce the wedge: serious self-directed investors get fund-style research workflows without institutional software budgets."
        actions={[
          { href: "/briefing", label: "Open Product" },
          { href: "/methodology", label: "Read Methodology", kind: "ghost" },
        ]}
      />

      <div className="grid-3">
        {pricingTiers.map((tier) => (
          <Panel key={tier.name} title={`${tier.name} ${tier.price}`} eyebrow="Tier">
            <p className="hero-copy">{tier.summary}</p>
            <ul className="bullet-stack">
              {tier.features.map((feature) => (
                <li key={feature}>{feature}</li>
              ))}
            </ul>
          </Panel>
        ))}
      </div>
    </Shell>
  );
}

