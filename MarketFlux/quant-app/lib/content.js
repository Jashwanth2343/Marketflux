export const featureContent = {
  "daily-brief": {
    title: "Daily Brief",
    summary: "A public version of a hedge-fund morning note, tuned for serious retail investors.",
    bullets: [
      "Macro regime framing before security-level interpretation.",
      "Top quant signals ranked by severity and freshness.",
      "Watchlist updates with explicit why-it-matters context.",
    ],
  },
  "filing-intelligence": {
    title: "Filing Intelligence",
    summary: "Surface what changed in 10-K, 10-Q, 8-K, and proxy filings without forcing users to read every page first.",
    bullets: [
      "Structured SEC metrics and document-change review.",
      "Fresh risk-factor and guidance review.",
      "Document-backed citations for every insight.",
    ],
  },
  "earnings-intelligence": {
    title: "Earnings Intelligence",
    summary: "Turn transcripts into evidence-backed highlights, not generic recap paragraphs.",
    bullets: [
      "Management confidence and quote extraction.",
      "Repeated analyst concern tracking.",
      "Transcript highlights embedded into the research workspace.",
    ],
  },
  "macro-regime": {
    title: "Macro Regime",
    summary: "Cross-asset, rate, and labor-aware market framing for every morning session.",
    bullets: [
      "Fed, curve, labor, and volatility context in one place.",
      "Regime labels that connect directly to sector implications.",
      "A shared risk-on, risk-off, and divergence lens across the app.",
    ],
  },
  "insider-clusters": {
    title: "Insider Clusters",
    summary: "Separate real insider signal from low-quality filing noise.",
    bullets: [
      "Cluster detection for repeated or multi-insider activity.",
      "Single-stock and sector-level insider context.",
      "Integrated into watchlists and research workspaces.",
    ],
  },
};

export const pricingTiers = [
  {
    name: "Observer",
    price: "$0",
    summary: "Market structure, methodology, and public compare pages.",
    features: [
      "Public product pages",
      "Methodology access",
      "Select daily market notes",
    ],
  },
  {
    name: "Research Desk",
    price: "$19",
    summary: "The core AI-native quant workflow for self-directed investors.",
    features: [
      "Morning Brief",
      "Signals feed",
      "Research workspace",
      "Watchlist board",
      "Saved theses",
    ],
  },
  {
    name: "Deep Research",
    price: "$49",
    summary: "Higher-intensity research runs with deeper document workflows and portfolio overlays.",
    features: [
      "Premium deep-dive runs",
      "Expanded compare workflows",
      "Priority signal history",
      "Advanced portfolio diagnostics",
    ],
  },
];

export const competitorContent = {
  finchat: {
    name: "FinChat",
    audience: "Investors who want a polished AI-first equity research flow.",
    strengths: [
      "Strong AI-assisted stock research interface.",
      "Friendly workflow for asking company-level questions quickly.",
    ],
    weaknesses: [
      "Less explicitly workflow-driven around signals and regime context.",
      "Not positioned as a public quant research operating system.",
    ],
    bestFor: "Fast equity research conversations.",
    marketFluxEdge: "MarketFlux leads with morning brief, signals, cross-asset context, and watchlist-centered research memory.",
  },
  tikr: {
    name: "TIKR",
    audience: "Fundamental investors who want transcripts, estimates, and broad company coverage.",
    strengths: [
      "Strong transcript and financial data workflow.",
      "Serious research coverage for company-level work.",
    ],
    weaknesses: [
      "Less opinionated about AI-native signal discovery.",
      "Less focused on proactive, quant-style market framing.",
    ],
    bestFor: "Deep fundamental research and transcript review.",
    marketFluxEdge: "MarketFlux adds a signal engine, macro regime framing, and saved thesis workflows around the core research surface.",
  },
  koyfin: {
    name: "Koyfin",
    audience: "Macro-aware investors who want visual market dashboards and screening.",
    strengths: [
      "Strong dashboarding and market-monitoring feel.",
      "Useful for scanning and chart-led workflows.",
    ],
    weaknesses: [
      "Less research-memory centric.",
      "Less explicitly AI-native for document intelligence.",
    ],
    bestFor: "Market monitoring and visual exploration.",
    marketFluxEdge: "MarketFlux pushes further into filing, transcript, insider, and thesis-linked workflows.",
  },
  "alpha-sense": {
    name: "AlphaSense",
    audience: "Professional teams that need premium, unified research intelligence.",
    strengths: [
      "Very strong qualitative and quantitative research positioning.",
      "Broad document intelligence across filings, transcripts, expert research, and news.",
    ],
    weaknesses: [
      "Enterprise-oriented cost and workflow expectations.",
      "Overkill for serious retail users who want fund-style rigor without institutional budgets.",
    ],
    bestFor: "Professional research organizations.",
    marketFluxEdge: "MarketFlux offers the same product ambition for a public, serious-retail audience with much lighter cost and simpler workflows.",
  },
  "bloomberg-terminal": {
    name: "Bloomberg Terminal",
    audience: "Institutional professionals who need all-in-one market data and execution-adjacent workflows.",
    strengths: [
      "Institutional depth, breadth, and workflow reach.",
      "A true category benchmark for research infrastructure.",
    ],
    weaknesses: [
      "Far too expensive and complex for most public investors.",
      "Not built around lightweight AI-native retail research workflows.",
    ],
    bestFor: "Large professional finance teams.",
    marketFluxEdge: "MarketFlux is the public quant-research alternative: narrower, more focused, and radically more accessible.",
  },
};

export const productPillars = [
  {
    eyebrow: "Systematic Signals",
    title: "A feed that thinks like a research desk",
    summary: "Signals are ranked, timestamped, and evidence-backed so users know what deserves attention first.",
  },
  {
    eyebrow: "Research Memory",
    title: "Every insight traces back to evidence",
    summary: "Citations, freshness, and thesis state travel with the workflow instead of disappearing into chat history.",
  },
  {
    eyebrow: "Public Quant Access",
    title: "Hedge-fund rigor without hedge-fund opacity",
    summary: "The goal is not to imitate a broker. It is to expose institutional research advantages to the public.",
  },
];

