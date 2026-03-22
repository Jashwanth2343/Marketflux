const API_BASE = process.env.MARKETFLUX_API_URL || "http://localhost:8001";

async function fetchBackendJson(path, fallback) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      next: { revalidate: 0 },
    });
    if (!response.ok) {
      return fallback;
    }
    return await response.json();
  } catch (error) {
    return fallback;
  }
}

export async function getBriefing() {
  return fetchBackendJson("/api/vnext/briefing/today", {
    macro_regime: {
      regime: "transitional",
      confidence: 61,
      summary: "Fallback briefing: the new API is not reachable yet, so the app is rendering a static preview of the Morning Brief experience.",
      key_indicators: [],
      sector_implications: [],
      cross_asset_view: [],
    },
    top_signals: [],
    watchlist_updates: [],
    top_movers: { gainers: [], losers: [] },
    methodology: {
      model_lane: {
        tier: 0,
        lane: "fallback preview",
      },
    },
  });
}

export async function getSignals() {
  return fetchBackendJson("/api/vnext/signals/feed", {
    as_of: new Date().toISOString(),
    signals: [],
  });
}

export async function getWorkspace(ticker) {
  return fetchBackendJson(`/api/vnext/research/ticker/${ticker}`, {
    ticker,
    as_of: new Date().toISOString(),
    snapshot: { symbol: ticker, name: ticker },
    technicals: {},
    macro_context: {},
    filings: { summary: "Backend unavailable." },
    transcripts: { summary: "Backend unavailable." },
    insider: { summary: "Backend unavailable." },
    thesis: { bull_case: [], base_case: [], bear_case: [], confidence: 0 },
    news: [],
    open_questions: [],
    citations: [],
    model_lane: { lane: "fallback preview", estimated_cost_usd: 0 },
  });
}

export async function getWatchlistBoard() {
  return fetchBackendJson("/api/vnext/watchlists/board", {
    as_of: new Date().toISOString(),
    watchlist_id: "public",
    items: [],
    saved_theses: [],
    citations: [],
  });
}

export async function getPortfolioDiagnostics() {
  return fetchBackendJson("/api/vnext/portfolio/diagnostics", {
    as_of: new Date().toISOString(),
    total_value: 0,
    concentration_risk: "No holdings on file yet.",
    macro_sensitivity: "Unavailable",
    sector_exposure: [],
    holdings: [],
    insights: [],
    citations: [],
  });
}

export async function getCompare(tickers) {
  return fetchBackendJson(`/api/vnext/compare?tickers=${encodeURIComponent(tickers.join(","))}`, {
    as_of: new Date().toISOString(),
    tickers,
    rows: [],
    citations: [],
  });
}

