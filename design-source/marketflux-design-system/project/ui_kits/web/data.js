// Static demo data for the MarketFlux UI kit.
// Numbers are realistic-shaped, not live.

window.MF_DATA = {
  asOf: '14:32 UTC · 14 NOV 2026',

  indices: [
    { sym: 'SPX',     name: 'S&P 500',      px: 5892.40,  chg: +38.21,  pct: +0.65 },
    { sym: 'NDX',     name: 'NASDAQ 100',   px: 20492.18, chg: +171.04, pct: +0.84 },
    { sym: 'DJI',     name: 'DOW JONES',    px: 43221.55, chg: -90.81,  pct: -0.21 },
    { sym: 'RUT',     name: 'RUSSELL 2000', px: 2342.18,  chg: +12.40,  pct: +0.53 },
    { sym: 'VIX',     name: 'VIX',          px: 29.49,    chg: +5.70,   pct: +24.00, isVol: true },
    { sym: 'BTC',     name: 'BITCOIN',      px: 67840,    chg: +1452,   pct: +2.18 },
    { sym: 'ETH',     name: 'ETHEREUM',     px: 3418.22,  chg: +35.18,  pct: +1.04 },
    { sym: 'EURUSD',  name: 'EUR/USD',      px: 1.0843,   chg: -0.0020, pct: -0.18 },
    { sym: 'US10Y',   name: '10Y YIELD',    px: 4.32,     chg: +0.08,   pct: +1.89 },
  ],

  gainers: [
    { sym: 'NVDA', name: 'Nvidia Corp.',           px: 1182.40, pct: +4.18 },
    { sym: 'AVGO', name: 'Broadcom Inc.',          px: 184.22,  pct: +3.51 },
    { sym: 'MSFT', name: 'Microsoft',              px: 412.66,  pct: +2.84 },
    { sym: 'AAPL', name: 'Apple Inc.',             px: 192.35,  pct: +2.09 },
    { sym: 'GOOGL',name: 'Alphabet',               px: 184.04,  pct: +1.92 },
    { sym: 'META', name: 'Meta Platforms',         px: 612.18,  pct: +1.68 },
    { sym: 'V',    name: 'Visa Inc.',              px: 312.40,  pct: +1.04 },
    { sym: 'LLY',  name: 'Eli Lilly',              px: 824.55,  pct: +0.92 },
  ],

  losers: [
    { sym: 'INTC', name: 'Intel Corp.',            px: 22.18,   pct: -4.22 },
    { sym: 'TSLA', name: 'Tesla Inc.',             px: 182.04,  pct: -3.41 },
    { sym: 'BAC',  name: 'Bank of America',        px: 41.82,   pct: -1.82 },
    { sym: 'AMZN', name: 'Amazon',                 px: 185.22,  pct: -1.03 },
    { sym: 'JPM',  name: 'JPMorgan Chase',         px: 232.04,  pct: -0.62 },
    { sym: 'XOM',  name: 'Exxon Mobil',            px: 118.40,  pct: -0.48 },
    { sym: 'PG',   name: 'Procter & Gamble',       px: 166.22,  pct: -0.31 },
  ],

  heatmap: {
    Technology: [
      { sym: 'NVDA', px: 1182.40, pct: +4.18, weight: 4 },
      { sym: 'AAPL', px: 192.35,  pct: +2.09, weight: 4 },
      { sym: 'MSFT', px: 412.66,  pct: +2.84, weight: 4 },
      { sym: 'AVGO', px: 184.22,  pct: +3.51, weight: 2 },
      { sym: 'GOOGL',px: 184.04,  pct: +1.92, weight: 2 },
      { sym: 'META', px: 612.18,  pct: +1.68, weight: 2 },
      { sym: 'AMD',  px: 142.18,  pct: +0.82, weight: 1 },
      { sym: 'CRM',  px: 312.40,  pct: -0.41, weight: 1 },
      { sym: 'ORCL', px: 168.22,  pct: +0.31, weight: 1 },
      { sym: 'INTC', px: 22.18,   pct: -4.22, weight: 1 },
    ],
    Financials: [
      { sym: 'JPM',  px: 232.04, pct: -0.62, weight: 2 },
      { sym: 'V',    px: 312.40, pct: +1.04, weight: 2 },
      { sym: 'MA',   px: 502.18, pct: +0.84, weight: 2 },
      { sym: 'BAC',  px: 41.82,  pct: -1.82, weight: 1 },
      { sym: 'WFC',  px: 72.40,  pct: -0.41, weight: 1 },
      { sym: 'GS',   px: 542.18, pct: +0.62, weight: 1 },
    ],
    Healthcare: [
      { sym: 'LLY',  px: 824.55, pct: +0.92, weight: 3 },
      { sym: 'UNH',  px: 612.40, pct: -0.41, weight: 2 },
      { sym: 'JNJ',  px: 162.18, pct: +0.21, weight: 1 },
      { sym: 'PFE',  px: 28.40,  pct: -1.03, weight: 1 },
    ],
  },

  news: [
    {
      id: 'n1', sentiment: 'BULLISH', sentClass: 'bull',
      tickers: ['NVDA', 'AAPL'],
      title: 'Nvidia beats on Q3 earnings, raises forward guidance on AI chip demand',
      source: 'Reuters', when: '2m ago',
    },
    {
      id: 'n2', sentiment: 'BEARISH', sentClass: 'bear',
      tickers: ['TSLA'],
      title: 'Tesla delivery numbers miss analyst estimates for third consecutive quarter',
      source: 'Bloomberg', when: '14m ago',
    },
    {
      id: 'n3', sentiment: 'NEUTRAL', sentClass: 'warn',
      tickers: ['SPX'],
      title: 'Fed minutes signal patience on rate cuts as inflation cools toward target',
      source: 'WSJ', when: '38m ago',
    },
    {
      id: 'n4', sentiment: 'BULLISH', sentClass: 'bull',
      tickers: ['META'],
      title: 'Meta unveils new AI infrastructure roadmap; capex guidance lifts shares',
      source: 'CNBC', when: '1h ago',
    },
  ],

  fearGreed: { score: 82, label: 'EXTREME GREED', momentum: 'BULLISH', vix: 29.49, vixDelta: +24, breadth: 62 },

  // AI Daily Brief — the synthesized "what matters today" feed.
  // Replaces the heatmap + fear/greed gauge as the dashboard's research brain.
  brief: {
    asOf: 'Today · 14:32 UTC',
    confidence: 86,
    summary: 'Risk-on tone holds. AI-chip strength (NVDA beat) is carrying tech, while Tesla deliveries and a softer DJI keep breadth uneven. Watch the 10Y at 4.32% — the only thing standing between this tape and a clean breakout.',
    items: [
      {
        id: 'b1', rank: 1, sentClass: 'bull', tag: 'BULLISH', tickers: ['NVDA', 'AVGO'],
        headline: 'AI-chip complex is leading — and the move has breadth',
        detail: 'Nvidia\'s guidance raise pulled Broadcom and the broader semis higher. Datacenter run-rate is the signal, not the print.',
        action: 'Open NVDA thesis', go: ['stock', 'NVDA'],
      },
      {
        id: 'b2', rank: 2, sentClass: 'warn', tag: 'WATCH', tickers: ['US10Y', 'SPX'],
        headline: '10Y yield at 4.32% is the swing factor',
        detail: 'Fed minutes signalled patience. A move above 4.40% would pressure multiples; below 4.20% likely fuels the next leg up.',
        action: 'See rate impact', go: ['screener'],
      },
      {
        id: 'b3', rank: 3, sentClass: 'bear', tag: 'BEARISH', tickers: ['TSLA'],
        headline: 'Tesla deliveries miss — third straight quarter',
        detail: 'Demand softness is now a trend, not a blip. FSD optionality is the only bull case; margins need to stabilise first.',
        action: 'Open TSLA thesis', go: ['stock', 'TSLA'],
      },
    ],
  },

  // Candle data for stock detail — 28 sessions of OHLC
  stockHistory: (() => {
    const out = []; let last = 178;
    for (let i = 0; i < 28; i++) {
      const drift = (Math.sin(i * 0.5) + (Math.random() - 0.5) * 1.5) * 2;
      const o = last;
      const c = +(o + drift).toFixed(2);
      const h = +(Math.max(o, c) + Math.random() * 1.6).toFixed(2);
      const l = +(Math.min(o, c) - Math.random() * 1.6).toFixed(2);
      out.push({ o, h, l, c });
      last = c;
    }
    return out;
  })(),

  ai: {
    insights: [
      { sym: 'AAPL', conf: 84, view: 'BULLISH', target: 210, horizon: '12M',
        thesis: 'Q3 earnings, technical signals, and supply‑chain data indicate continued growth. Services revenue inflecting; valuation reasonable at 28x fwd.' },
      { sym: 'TSLA', conf: 62, view: 'NEUTRAL', target: 195, horizon: '6M',
        thesis: 'Delivery weakness offset by FSD optionality. Wait for margin stabilisation.' },
      { sym: 'NVDA', conf: 91, view: 'BULLISH', target: 1400, horizon: '12M',
        thesis: 'Datacenter run-rate accelerating. Blackwell ramp ahead of schedule. AI capex from hyperscalers remains resilient.' },
    ],
  },

  // Screener results — used in AI Screener screen
  screenerResults: [
    { sym: 'AAPL',  name: 'Apple Inc.',          mcap: '3.02T',  pe: 28.2,  px: 192.35, pct: +2.09, sector: 'Technology' },
    { sym: 'GOOGL', name: 'Alphabet',            mcap: '2.28T',  pe: 22.1,  px: 184.04, pct: +1.92, sector: 'Technology' },
    { sym: 'META',  name: 'Meta Platforms',      mcap: '1.54T',  pe: 24.4,  px: 612.18, pct: +1.68, sector: 'Technology' },
    { sym: 'CRM',   name: 'Salesforce',          mcap: '298B',   pe: 31.2,  px: 312.40, pct: -0.41, sector: 'Technology' },
    { sym: 'ORCL',  name: 'Oracle Corp.',        mcap: '462B',   pe: 26.8,  px: 168.22, pct: +0.31, sector: 'Technology' },
    { sym: 'IBM',   name: 'IBM',                 mcap: '198B',   pe: 18.4,  px: 215.40, pct: +0.84, sector: 'Technology' },
    { sym: 'CSCO',  name: 'Cisco Systems',       mcap: '226B',   pe: 16.9,  px: 56.18,  pct: -0.22, sector: 'Technology' },
  ],
};
