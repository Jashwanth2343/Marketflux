// MarketFlux Agents — fake agent data, modelled on Public.com's
// agentic brokerage examples but adapted to the MarketFlux product.

window.MF_AGENTS = [
  {
    id: 'a1', status: 'active',
    title: 'CPI hedge',
    prompt: 'Sell 10% of my consumer staples positions and reinvest into high-growth tech if next CPI prints above 4%.',
    tags: ['Market monitoring', 'Risk management'],
    runs: 3, nextCheck: 'Next CPI · 12 Jun 2026',
  },
  {
    id: 'a2', status: 'active',
    title: '$5k covered calls',
    prompt: 'Sell 10 covered calls monthly on FLYF (strike $50, 30 DTE).',
    tags: ['Trading strategy', 'Options'],
    runs: 48, nextCheck: 'First trading day of month',
  },
  {
    id: 'a3', status: 'active',
    title: 'Retail therapy',
    prompt: 'Track my retail holdings. When they are all down 15% from 30-day high, buy $100 of each.',
    tags: ['Trading strategy', 'Market monitoring'],
    runs: 12, nextCheck: 'Hourly · holdings: 8',
  },
  {
    id: 'a4', status: 'active',
    title: 'Idle cash sweep',
    prompt: 'Sweep any cash over $20,000 from checking into my bond account.',
    tags: ['Fund management'],
    runs: 24, nextCheck: 'Daily · 16:30 EST',
  },
  {
    id: 'a5', status: 'active',
    title: 'BTC EMA dip',
    prompt: 'Every 15 minutes, check if BTC is below its 50-day EMA. Buy $2,000 at market.',
    tags: ['Trading strategy', 'Crypto'],
    runs: 1488, nextCheck: 'Every 15 min',
  },
  {
    id: 'a6', status: 'paused',
    title: 'Fed rate cut',
    prompt: 'If the Fed cuts rates, trim 10% of bank stocks and rotate into my high-growth tech holdings.',
    tags: ['Market monitoring', 'Risk management'],
    runs: 0, nextCheck: 'Paused by you',
  },
  {
    id: 'a7', status: 'active',
    title: 'USO spike protection',
    prompt: 'Whenever USO spikes 5% weekly, increase all my energy positions by 5%.',
    tags: ['Market monitoring', 'Risk management'],
    runs: 6, nextCheck: 'Weekly · close Friday',
  },
  {
    id: 'a8', status: 'draft',
    title: 'Down payment cash',
    prompt: 'Free up cash by trimming $3,500 from my tech stocks every week.',
    tags: ['Fund management', 'Trading strategy'],
    runs: 0, nextCheck: 'Draft · review required',
  },
  {
    id: 'a9', status: 'coming-soon',
    title: 'Presidential pump',
    prompt: 'When the President posts positive sentiment around a stock, buy $5,000 worth.',
    tags: ['Market monitoring', 'Sentiment'],
    runs: 0, nextCheck: 'Coming Q3 2026',
  },
];

window.MF_AGENT_CAPABILITIES = [
  { icon: 'line-chart',  title: 'Trading strategies', items: ['Equities, options, crypto', 'Market & limit orders', 'Multi-leg options', 'Rolling positions', 'Stop-loss · OCO · trailing'] },
  { icon: 'activity',    title: 'Indicators',         items: ['EMA · SMA · RSI · MACD', 'Bollinger Bands', 'Average True Range', 'Volume + 1D price change'] },
  { icon: 'database',    title: 'Data sources',       items: ['Real-time price feeds', 'VIX & macro indicators', 'ETF / Index constituents', 'Earnings & dividends', 'Fear & Greed Index'] },
  { icon: 'wallet',      title: 'Cash management',    items: ['Internal sweeps', 'External deposits', 'Dividend re-investing', 'Rebalancing'] },
];

window.MF_AGENT_PROMPTS = [
  'If VIX hits 25, buy a put on SPY worth $1,000.',
  'When AAPL drops 5% intraday, buy $500 and notify me.',
  'Sweep any bonus deposit into the 4-week T-Bill ladder.',
];

/* ===================================================================
   AGENT WORKSPACE — data for the live agent detail view.
   Shared datasets that back the dockable widgets. Numbers are
   realistic-shaped, not live.
   =================================================================== */
window.MF_AGENT_WIDGETS_DATA = {
  // Options chain (pro-terminal dense), centred near SPY ~ $580
  optionsChain: {
    underlying: 'SPY', spot: 581.24, expiry: '20 Jun 2026', dte: 22,
    rows: [
      { strike: 570, cBid: 14.82, cAsk: 15.10, cDelta: 0.78, pBid: 3.10, pAsk: 3.28, pDelta: -0.22, target: false },
      { strike: 575, cBid: 11.40, cAsk: 11.68, cDelta: 0.69, pBid: 4.55, pAsk: 4.74, pDelta: -0.31, target: false },
      { strike: 580, cBid: 8.42,  cAsk: 8.66,  cDelta: 0.57, pBid: 6.58, pAsk: 6.80, pDelta: -0.43, target: false },
      { strike: 585, cBid: 5.90,  cAsk: 6.12,  cDelta: 0.44, pBid: 9.05, pAsk: 9.30, pDelta: -0.56, target: true  },
      { strike: 590, cBid: 3.92,  cAsk: 4.10,  cDelta: 0.31, pBid: 12.1, pAsk: 12.4, pDelta: -0.69, target: false },
      { strike: 595, cBid: 2.45,  cAsk: 2.62,  cDelta: 0.21, pBid: 15.6, pAsk: 15.9, pDelta: -0.79, target: false },
    ],
  },
  positions: [
    { sym: 'SPY',  qty: 120, avg: 548.10, last: 581.24, plPct: +6.05 },
    { sym: 'NVDA', qty: 40,  avg: 940.00, last: 1182.40, plPct: +25.79 },
    { sym: 'AAPL', qty: 80,  avg: 191.20, last: 185.22, plPct: -3.13 },
    { sym: 'XLP',  qty: 60,  avg: 82.40,  last: 80.05,  plPct: -2.85 },
  ],
  cash: { buyingPower: 48250, settled: 22180, sweepTarget: 20000, idle: 2180, allocated: 26070 },
  activity: [
    { t: '14:32:09', kind: 'eval',   text: 'Condition check — VIX 29.49 > 25 ✓' },
    { t: '14:32:08', kind: 'data',   text: 'Pulled SPY chain · 6 strikes · IV 18.4%' },
    { t: '14:31:55', kind: 'think',  text: 'Selected 585P · Δ −0.56 · 22 DTE' },
    { t: '14:30:00', kind: 'idle',   text: 'Heartbeat — monitoring 1 condition' },
    { t: '14:15:00', kind: 'idle',   text: 'Heartbeat — monitoring 1 condition' },
  ],
  market: [
    { sym: 'VIX',  px: 29.49, pct: +24.18, alert: true },
    { sym: 'SPX',  px: 5874.2, pct: -0.62 },
    { sym: 'QQQ',  px: 504.18, pct: -0.41 },
    { sym: 'DXY',  px: 104.82, pct: +0.18 },
    { sym: 'US10Y', px: 4.32, pct: +0.04, unit: '%' },
  ],
  guardrails: [
    { label: 'Max position size', value: '$1,000', ok: true },
    { label: 'Daily loss limit',  value: '$2,500', ok: true },
    { label: 'Requires approval', value: 'Off · auto-execute', ok: true },
    { label: 'Trading window',    value: 'RTH only', ok: true },
  ],
};

// The catalogue of widgets a user can dock. `default` = shown on open.
window.MF_AGENT_WIDGET_CATALOG = [
  { id: 'options',    title: 'Options Hub',      icon: 'layers',      default: true,  side: 'right' },
  { id: 'positions',  title: 'Positions',        icon: 'briefcase',   default: true,  side: 'right' },
  { id: 'market',     title: 'Market context',   icon: 'activity',    default: true,  side: 'left'  },
  { id: 'cash',       title: 'Cash & buying power', icon: 'wallet',   default: true,  side: 'left'  },
  { id: 'activity',   title: 'Activity log',     icon: 'list',        default: true,  side: 'right' },
  { id: 'guardrails', title: 'Risk guardrails',  icon: 'shield',      default: true,  side: 'left'  },
  { id: 'news',       title: 'Related news',     icon: 'newspaper',   default: false, side: 'right' },
  { id: 'pnl',        title: 'Strategy P&L',     icon: 'trending-up', default: false, side: 'left'  },
];

// Per-agent run scripts (the animated execution timeline). Steps stream
// pending → running → done. `log` lines appear while a step runs.
window.MF_AGENT_RUNS = {
  a1: [
    { label: 'Watch CPI release calendar', detail: 'Next print: 12 Jun 2026, 08:30 ET', log: ['Subscribed to BLS CPI feed', 'Last CPI: 3.4% YoY'] },
    { label: 'Evaluate CPI vs 4% threshold', detail: 'Trigger if YoY > 4.0%', log: ['Awaiting release…'] },
    { label: 'Sell 10% of consumer staples', detail: 'XLP, KO, PG — market orders', log: [] },
    { label: 'Rotate proceeds into growth tech', detail: 'NVDA, MSFT — weighted by conviction', log: [] },
    { label: 'Notify & log to activity feed', detail: 'Push + email on fill', log: [] },
  ],
  default: [
    { label: 'Monitor market conditions', detail: 'Polling every 60s', log: ['Connected to real-time feed', 'Baseline snapshot captured'] },
    { label: 'Evaluate trigger condition', detail: 'VIX > 25', log: ['VIX 29.49 — condition met ✓'] },
    { label: 'Resolve instrument & size', detail: 'SPY 585P · $1,000 budget', log: ['Pulled options chain', 'Selected 585P · Δ −0.56'] },
    { label: 'Stage order for execution', detail: 'Limit @ mid · RTH only', log: ['Pre-trade risk check passed'] },
    { label: 'Execute & notify', detail: 'Fill confirmation + activity log', log: ['Order routed', 'Filled · 2 contracts @ $9.18'] },
  ],
};
