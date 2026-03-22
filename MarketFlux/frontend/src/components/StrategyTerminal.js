import { useMemo, useRef, useState, useEffect } from 'react';
import {
  Bot,
  BrainCircuit,
  Loader2,
  Play,
  ShieldAlert,
  Sparkles,
  TerminalSquare,
  X,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { API_BASE } from '@/lib/api';

const PRESET_PROMPTS = [
  "Build a live swing strategy for NVDA using current macro regime, filings, technicals, and risk controls.",
  "Generate a market-neutral pair trade using the strongest live momentum name versus the weakest laggard.",
  "Create a defensive hedge strategy for a growth-heavy portfolio if the macro regime shifts risk-off.",
];

function toneForConfidence(confidence) {
  if (confidence >= 72) return 'border-primary/20 bg-primary/10 text-primary';
  if (confidence >= 58) return 'border-amber-400/20 bg-amber-400/10 text-amber-300';
  return 'border-rose-400/20 bg-rose-400/10 text-rose-300';
}

import { useNavigate, useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';

export default function StrategyTerminal() {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState(PRESET_PROMPTS[0]);
  const [mode, setMode] = useState('swing');
  const [riskProfile, setRiskProfile] = useState('balanced');
  const [capitalBase, setCapitalBase] = useState('100000');
  const [allowShort, setAllowShort] = useState(true);
  const [loading, setLoading] = useState(false);
  const [thinkingSteps, setThinkingSteps] = useState([]);
  const [agentResults, setAgentResults] = useState([]);
  const [output, setOutput] = useState('');
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const strategySummary = useMemo(() => meta?.strategy || null, [meta]);
  const { strategyId } = useParams();

  useEffect(() => {
    if (strategyId) {
      loadStrategy(strategyId);
    }
  }, [strategyId]);

  const loadStrategy = async (id) => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${API_BASE}/api/fundos/strategies/${id}`, {
        headers: {
          Authorization: localStorage.getItem('mf_token') ? `Bearer ${localStorage.getItem('mf_token')}` : '',
        }
      });
      if (!res.ok) throw new Error("Failed to load historical strategy.");
      const data = await res.json();
      
      setAgentResults(data.evidence || []);
      if (data.model_trace && data.model_trace.raw_output) {
          setOutput(data.model_trace.raw_output);
      } else {
          setOutput(`**THESIS:** ${data.thesis}\n\n**ENTRY:** ${data.entry}\n\n**TARGET:** ${data.target}\n\n**STOP:** ${data.stop}\n\n**INVALIDATION:** ${data.invalidation}`);
      }
      
      let direction = 'PASS';
      const textCheck = (data.thesis || '').toLowerCase();
      if (textCheck.includes('long')) direction = 'LONG';
      else if (textCheck.includes('short')) direction = 'SHORT';
      
      setMeta({ strategy: { direction, confidence: data.confidence } });
      setPrompt(data.title || '');
    } catch (err) {
      console.error(err);
      setError("Failed to load historical strategy.");
    } finally {
      setLoading(false);
    }
  };

  const runStrategy = async () => {
    if (!prompt.trim() || loading) return;

    setLoading(true);
    setThinkingSteps([]);
    setAgentResults([]);
    setOutput('');
    setMeta(null);
    setError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(`${API_BASE}/api/fundos/terminal/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: localStorage.getItem('mf_token') ? `Bearer ${localStorage.getItem('mf_token')}` : '',
        },
        body: JSON.stringify({
          prompt,
          mode,
          risk_profile: riskProfile,
          capital_base: Number(capitalBase) || 100000,
          allow_short: allowShort,
        }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`Terminal request failed with status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      const processLine = (line) => {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data: ')) return;
        const payload = JSON.parse(trimmed.slice(6));
        if (payload.type === 'thinking') {
          setThinkingSteps((prev) => [...prev, { step: payload.step, message: payload.message }]);
        } else if (payload.type === 'agent') {
          setAgentResults((prev) => {
            const next = [...prev];
            const index = next.findIndex((item) => item.agent_id === payload.agent.agent_id);
            if (index >= 0) next[index] = payload.agent;
            else next.push(payload.agent);
            return next;
          });
        } else if (payload.type === 'token') {
          setOutput((prev) => prev + (payload.content || ''));
        } else if (payload.type === 'done') {
          setMeta(payload);
          if (payload.status && payload.status !== 'ok') {
            setError(payload.message || 'Provider configuration is missing.');
          }
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        buffer += value ? decoder.decode(value, { stream: !done }) : '';
        const lines = buffer.split('\n');
        buffer = done ? '' : (lines.pop() || '');
        for (const line of lines) {
          processLine(line);
        }
        if (done) break;
      }
      if (buffer.trim()) {
        processLine(buffer);
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('Strategy terminal error:', err);
        setError(err.message || 'Unable to generate strategy.');
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  };

  const stopRun = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
  };

  return (
    <div className="flex flex-col min-h-full w-full bg-[#05080A] overflow-y-auto">
      <div className="flex flex-1 flex-col w-full min-h-[800px]">
        <div className="flex items-center justify-between border-b border-white/8 px-5 py-4">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
              <TerminalSquare className="w-4 h-4 text-primary" />
              Strategy Terminal
            </div>
            <div className="mt-2 flex items-center gap-3">
              <h2 className="fundos-display text-2xl font-semibold text-foreground">Agentic trade studio</h2>
              {strategySummary && (
                <span className={`rounded-full border px-3 py-1 text-[11px] font-mono uppercase tracking-[0.14em] ${toneForConfidence(strategySummary.confidence || 50)}`}>
                  {strategySummary.confidence || 50}/100
                </span>
              )}
            </div>
          </div>
          <button onClick={() => navigate('/fund-os')} className="rounded-full border border-white/10 bg-white/5 p-2 text-muted-foreground hover:text-foreground">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid flex-1 gap-0 lg:grid-cols-[360px_1fr]">
          <div className="border-b border-white/8 p-5 lg:border-b-0 lg:border-r">
            <div className="space-y-4">
              <div>
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Prompt</div>
                <textarea
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  className="mt-2 min-h-[180px] w-full rounded-[20px] border border-white/10 bg-white/5 px-4 py-4 text-sm leading-7 text-foreground outline-none transition-colors focus:border-primary/30"
                  placeholder="Describe the strategy you want the swarm to build..."
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Mode</div>
                  <select value={mode} onChange={(event) => setMode(event.target.value)} className="mt-2 h-11 w-full rounded-[16px] border border-white/10 bg-white/5 px-3 text-sm text-foreground outline-none">
                    <option value="swing">Swing</option>
                    <option value="intraday">Intraday</option>
                    <option value="hedge">Hedge</option>
                    <option value="pair">Pair trade</option>
                  </select>
                </div>
                <div>
                  <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Risk</div>
                  <select value={riskProfile} onChange={(event) => setRiskProfile(event.target.value)} className="mt-2 h-11 w-full rounded-[16px] border border-white/10 bg-white/5 px-3 text-sm text-foreground outline-none">
                    <option value="conservative">Conservative</option>
                    <option value="balanced">Balanced</option>
                    <option value="aggressive">Aggressive</option>
                  </select>
                </div>
              </div>

              <div>
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Capital base</div>
                <input
                  value={capitalBase}
                  onChange={(event) => setCapitalBase(event.target.value)}
                  className="mt-2 h-11 w-full rounded-[16px] border border-white/10 bg-white/5 px-3 text-sm text-foreground outline-none"
                  placeholder="100000"
                />
              </div>

              <label className="flex items-center gap-3 rounded-[18px] border border-white/10 bg-white/5 px-4 py-3 text-sm text-foreground">
                <input type="checkbox" checked={allowShort} onChange={(event) => setAllowShort(event.target.checked)} />
                Allow short and hedge structures
              </label>

              <div className="space-y-2">
                {PRESET_PROMPTS.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => setPrompt(preset)}
                    className="w-full rounded-[18px] border border-white/10 bg-white/4 px-4 py-3 text-left text-sm leading-6 text-muted-foreground hover:border-primary/20 hover:bg-primary/10 hover:text-foreground"
                  >
                    {preset}
                  </button>
                ))}
              </div>

              <div className="flex gap-3">
                <Button onClick={runStrategy} className="h-12 flex-1 rounded-full">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  Generate strategy
                </Button>
                <Button variant="outline" onClick={stopRun} disabled={!loading} className="h-12 rounded-full border-white/10 bg-white/5 text-foreground hover:bg-white/10">
                  Stop
                </Button>
              </div>

              {meta?.provider_plan && (
                <div className="rounded-[18px] border border-white/10 bg-white/4 p-4 text-sm">
                  <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Provider plan</div>
                  <div className="mt-2 text-foreground">{meta.provider_plan.provider}</div>
                  <div className="mt-1 text-muted-foreground">{meta.provider_plan.reasoning_model}</div>
                </div>
              )}
            </div>
          </div>

          <div className="flex min-h-0 flex-col">
            <div className="grid gap-4 border-b border-white/8 px-5 py-4 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-[18px] border border-white/10 bg-white/4 p-4">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Swarm status</div>
                <div className="mt-2 flex items-center gap-2 text-foreground">
                  <Bot className="w-4 h-4 text-primary" />
                  {loading ? 'Running' : 'Idle'}
                </div>
              </div>
              <div className="rounded-[18px] border border-white/10 bg-white/4 p-4">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Agents completed</div>
                <div className="mt-2 text-foreground">{agentResults.length}</div>
              </div>
              <div className="rounded-[18px] border border-white/10 bg-white/4 p-4">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Run mode</div>
                <div className="mt-2 text-foreground">{mode}</div>
              </div>
              <div className="rounded-[18px] border border-white/10 bg-white/4 p-4">
                <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Risk profile</div>
                <div className="mt-2 text-foreground">{riskProfile}</div>
              </div>
            </div>

            <div className="grid min-h-0 flex-1 gap-0 xl:grid-cols-[320px_1fr]">
              <div className="border-b border-white/8 p-5 xl:border-b-0 xl:border-r">
                <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                  <BrainCircuit className="w-4 h-4 text-primary" />
                  Agent debate
                </div>
                <div className="mt-4 space-y-3 overflow-y-auto pr-1">
                  {thinkingSteps.map((item, index) => (
                    <div key={`${item.step}-${index}`} className="rounded-[16px] border border-white/8 bg-white/4 px-4 py-3 text-sm text-muted-foreground">
                      <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-primary">{item.step}</div>
                      <div className="mt-1 leading-6">{item.message}</div>
                    </div>
                  ))}
                  {agentResults.map((agent) => (
                    <div key={agent.agent_id} className="rounded-[18px] border border-white/10 bg-white/5 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-semibold text-foreground">{agent.name}</div>
                        <div className={`rounded-full border px-2.5 py-1 text-[11px] font-mono uppercase tracking-[0.14em] ${toneForConfidence(agent.confidence)}`}>
                          {agent.confidence}/100
                        </div>
                      </div>
                      <div className="mt-2 text-muted-foreground prose prose-invert prose-sm max-w-none">
                        <ReactMarkdown>{agent.summary}</ReactMarkdown>
                      </div>
                      <div className="mt-3 text-[11px] font-mono uppercase tracking-[0.18em] text-primary">{agent.trade_expression}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex min-h-0 flex-col p-5">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                    <Sparkles className="w-4 h-4 text-primary" />
                    Final strategy output
                  </div>
                  {strategySummary && (
                    <div className={`rounded-full border px-3 py-1 text-[11px] font-mono uppercase tracking-[0.14em] ${toneForConfidence(strategySummary.confidence || 50)}`}>
                      {strategySummary.direction || 'neutral'}
                    </div>
                  )}
                </div>

                {error && (
                  <div className="mt-4 rounded-[18px] border border-rose-400/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-200">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4" />
                      {error}
                    </div>
                  </div>
                )}

                <div className="mt-4 min-h-0 flex-1 overflow-y-auto rounded-[24px] border border-white/10 bg-[rgba(255,255,255,0.03)] p-5">
                  {output ? (
                    <div className="text-sm leading-7 text-foreground prose prose-invert prose-sm max-w-none">
                      <ReactMarkdown>{output}</ReactMarkdown>
                    </div>
                  ) : (
                    <div className="flex h-full min-h-[360px] items-center justify-center text-center text-sm text-muted-foreground">
                      Run the terminal to generate a live strategy with macro, fundamental, market-structure, and risk agents.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
