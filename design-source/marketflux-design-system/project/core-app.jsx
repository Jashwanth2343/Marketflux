/* MarketFlux · Autonomous Core · app orchestrator */

// Babel script blocks are isolated scopes — rebind React hooks here.
const { useState, useEffect, useRef, useMemo } = React;

const RUNS = [
  { id: 'mh3',     label: 'Build momentum hunter v3',           status: 'live' },
  { id: 'macro',   label: 'Macro briefing · CPI week',          status: 'ok' },
  { id: 'rebal',   label: 'Quarterly rebalance proposal',       status: 'ok' },
  { id: 'hedge',   label: 'Hedge SPY before earnings season',   status: 'ok' },
  { id: 'screen',  label: 'Find 3 oversold mid-caps insider buying', status: 'ok' },
  { id: 'brief',   label: 'Daily portfolio briefing · pre-open',status: 'ok' },
  { id: 'lab',     label: 'Test mean-reversion on QQQ basket',  status: 'idle' },
  { id: 'theses',  label: 'Update NVDA long-term thesis',       status: 'idle' },
];

const SUGGESTIONS = [
  { text: 'Run live on tomorrow\'s open', num: 1 },
  { text: 'Tighten stops to 1.5× ATR', num: 2 },
  { text: 'Add semiconductor sector filter', num: 3 },
];

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "leftRailOpen": true,
  "logExpanded": false,
  "dotDensity": "normal",
  "showAmbient": true,
  "activeRun": "mh3",
  "model": "gemini"
}/*EDITMODE-END*/;

function App() {
  const [tool, setTool] = useState('select');
  const [running, setRunning] = useState(true);
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // Agent log events (lightweight, for footer)
  const logEvents = useMemo(() => ([
    { t: '00.14', txt: 'flux.boot ok',                 tone: 'var(--fg-tertiary)' },
    { t: '00.48', txt: 'alpaca.connected',             tone: '#4ADE80' },
    { t: '00.72', txt: 'screener.run("rs>=90,...")',   tone: 'var(--fg-secondary)' },
    { t: '01.12', txt: '412 → 22 → 6 candidates ✓',    tone: '#4ADE80' },
    { t: '01.38', txt: 'news.scan(top_6, 24h)',        tone: 'var(--fg-secondary)' },
    { t: '01.90', txt: 'research ✓ 1.32s · 18 signals',tone: '#4ADE80' },
    { t: '02.36', txt: 'sizer.kelly_atr(0.8%)',        tone: 'var(--fg-secondary)' },
    { t: '02.62', txt: 'sizing ✓ qty=28 stop=-3.8%',   tone: '#4ADE80' },
    { t: '02.82', txt: 'orders.compose · 3 trades',    tone: 'var(--fg-secondary)' },
    { t: '03.42', txt: 'ready · awaiting approval',    tone: '#F5C147' },
  ]), []);

  return <>
    <TopBar agentName="Momentum Hunter v3" running={running}
      onMenu={() => setTweak('leftRailOpen', !t.leftRailOpen)}
      onRun={() => setRunning(r => !r)} />

    <LeftRail open={t.leftRailOpen}
      onClose={() => setTweak('leftRailOpen', false)}
      runs={RUNS} activeId={t.activeRun}
      onSelect={(id) => setTweak('activeRun', id)} />

    <Canvas layout={CARD_LAYOUT}
      leftRailOpen={t.leftRailOpen}
      dotDensity={t.dotDensity} />

    <ToolPalette tool={tool} setTool={setTool} />

    <BottomPrompt
      onSend={(txt) => { console.log('send:', txt); }}
      suggestions={SUGGESTIONS}
      model={t.model}
      onModelChange={(m) => setTweak('model', m)} />

    <AgentLogFooter events={logEvents}
      expanded={t.logExpanded}
      onToggle={() => setTweak('logExpanded', !t.logExpanded)} />

    <TweaksPanel title="Tweaks">
      <TweakSection label="Layout">
        <TweakToggle label="Left rail · agent runs" value={t.leftRailOpen}
          onChange={(v) => setTweak('leftRailOpen', v)} />
        <TweakToggle label="Agent log expanded" value={t.logExpanded}
          onChange={(v) => setTweak('logExpanded', v)} />
        <TweakToggle label="Ambient glow" value={t.showAmbient}
          onChange={(v) => setTweak('showAmbient', v)} />
      </TweakSection>
      <TweakSection label="Canvas">
        <TweakRadio label="Dot density" value={t.dotDensity}
          options={[
            { value: 'loose', label: 'Loose' },
            { value: 'normal', label: 'Normal' },
            { value: 'dense', label: 'Dense' },
          ]}
          onChange={(v) => setTweak('dotDensity', v)} />
      </TweakSection>
      <TweakSection label="Agent">
        <TweakSelect label="Model" value={t.model}
          options={[
            { value: 'gemini', label: 'Gemini 2.5 Pro' },
            { value: 'claude', label: 'Claude Sonnet 4.5' },
            { value: 'gpt',    label: 'GPT-5' },
          ]}
          onChange={(v) => setTweak('model', v)} />
      </TweakSection>
    </TweaksPanel>
  </>;
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
