import { useDemoMode } from '@/lib/demoMode';

export default function DemoBanner() {
  const demo = useDemoMode();
  if (!demo) return null;

  return (
    <div
      role="note"
      className="border-b border-[rgba(227,184,95,0.35)] bg-[rgba(227,184,95,0.12)] px-4 py-2 text-center text-[12px] font-medium tracking-wide text-[#E3B85F]"
    >
      Paper trading, not investment advice. Automatic execution is off on this public demo.
    </div>
  );
}
