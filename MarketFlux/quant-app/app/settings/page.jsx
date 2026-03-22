import { PageHero, Panel, Shell } from "@/components/shell";

export default function SettingsPage() {
  return (
    <Shell active="/settings">
      <PageHero
        eyebrow="Settings And Controls"
        title="Research controls should make cost, data, and automation explicit."
        summary="This page is where model budgets, signal preferences, alerts, and future NemoClaw-style bridge settings should live."
        actions={[
          { href: "/methodology", label: "Open Methodology" },
          { href: "/briefing", label: "Back To Briefing", kind: "ghost" },
        ]}
      />

      <div className="grid-2">
        <Panel title="Planned controls" eyebrow="Roadmap">
          <ul className="bullet-stack">
            <li>Model lane preferences and hard monthly budget caps.</li>
            <li>Alert severity thresholds by watchlist or signal type.</li>
            <li>Workspace integrations for external research services and future agent bridges.</li>
          </ul>
        </Panel>
        <Panel title="Innovation guardrails" eyebrow="Non-generic by design">
          <ul className="bullet-stack">
            <li>Signals must remain systematic before they become narrative.</li>
            <li>Document-backed research memory is mandatory for trust.</li>
            <li>Any future agent bridge should plug into this product surface, not replace it.</li>
          </ul>
        </Panel>
      </div>
    </Shell>
  );
}

