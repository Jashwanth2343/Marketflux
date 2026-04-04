import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  TrendingUp, TrendingDown, Activity, Search, Zap, BarChart3,
  Brain, AlertTriangle, RefreshCw, Target, Lightbulb, ChevronRight,
  Shield, Star, BookOpen, FlaskConical
} from 'lucide-react';
import api, { API_BASE } from '@/lib/api';

// --- Helpers ---
function signalColor(label) {
  if (!label) return 'text-muted-foreground';
  if (label.includes('STRONG BUY')) return 'text-[#00FF41]';
  if (label.includes('BUY')) return 'text-[#3FB950]';
  if (label.includes('STRONG SELL')) return 'text-[#F85149]';
  if (label.includes('SELL')) return 'text-[#F85149]';
  return 'text-[#00F3FF]';
}

function signalBgColor(label) {
  if (!label) return 'bg-muted/20';
  if (label.includes('STRONG BUY')) return 'bg-[#00FF41]/10 border-[#00FF41]/30';
  if (label.includes('BUY')) return 'bg-[#3FB950]/10 border-[#3FB950]/30';
  if (label.includes('STRONG SELL')) return 'bg-[#F85149]/10 border-[#F85149]/30';
  if (label.includes('SELL')) return 'bg-[#F85149]/10 border-[#F85149]/30';
  return 'bg-[#00F3FF]/10 border-[#00F3FF]/30';
}

function ScoreBar({ score }) {
  const pct = ((score + 100) / 200) * 100;
  const color = score >= 25 ? '#00FF41' : score >= -25 ? '#00F3FF' : '#F85149';
  return (
    <div className="w-full bg-muted/20 h-1.5 rounded-none mt-1">
      <div className="h-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function CategoryScore({ label, data }) {
  if (!data) return null;
  const score = data.score || 0;
  const color = score >= 25 ? '#00FF41' : score >= -25 ? '#00F3FF' : '#F85149';
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/20">
      <span className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">{label}</span>
      <div className="flex items-center gap-2">
        <div className="w-16 bg-muted/20 h-1 rounded-none">
          <div className="h-full" style={{ width: `${((score + 100) / 200) * 100}%`, background: color }} />
        </div>
        <span className="font-mono text-xs w-10 text-right" style={{ color }}>{score > 0 ? '+' : ''}{score}</span>
      </div>
    </div>
  );
}

function renderMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/\\(#{1,6}\s)/g, '$1')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^### (.*$)/gm, '<h3 style="font-size:0.85rem;font-weight:700;margin:0.75rem 0 0.35rem;color:#00FF41;font-family:monospace;">$1</h3>')
    .replace(/^## (.*$)/gm, '<h2 style="font-size:0.95rem;font-weight:800;margin:1rem 0 0.5rem;color:#00F3FF;font-family:monospace;">$1</h2>')
    .replace(/^# (.*$)/gm, '<h1 style="font-size:1.1rem;font-weight:800;margin:1rem 0 0.5rem;color:#00FF41;font-family:monospace;">$1</h1>')
    .replace(/^\- (.*$)/gm, '<li style="margin-left:1rem;margin-bottom:0.15rem;">$1</li>')
    .replace(/`([^`]+)`/g, '<code style="background:#1a1a1a;padding:0.1rem 0.25rem;font-family:monospace;font-size:0.8rem;">$1</code>')
    .replace(/\|(.+)\|/g, (match) => {
      const cells = match.split('|').filter(Boolean).map(c => c.trim());
      return '<tr>' + cells.map(c => `<td style="padding:3px 8px;border:1px solid #333;">${c}</td>`).join('') + '</tr>';
    })
    .replace(/\n\n/g, '</p><p style="margin-bottom:0.5rem;">')
    .replace(/\n/g, '<br/>');
}

// --- Signal Panel Component ---
function SignalPanel({ ticker }) {
  const [signals, setSignals] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchSignals = useCallback(async () => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get(`/research/signals/${ticker}`);
      setSignals(data);
    } catch (e) {
      setError('Failed to load signals');
    } finally {
      setLoading(false);
    }
  }, [ticker]);

  useEffect(() => { fetchSignals(); }, [fetchSignals]);

  if (loading) return (
    <div className="space-y-2">
      {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}
    </div>
  );

  if (error) return (
    <div className="rounded-none border border-destructive/30 bg-destructive/10 p-3">
      <p className="text-xs text-destructive font-mono">{error}</p>
      <p className="text-[10px] text-muted-foreground font-mono mt-1">Signal engine fallback active — retry in a few seconds.</p>
    </div>
  );
  if (!signals) return null;

  const cats = signals.categories || {};
  return (
    <div>
      <div className={`flex items-center justify-between mb-3 p-2 border rounded-none ${signalBgColor(signals.signal_label)}`}>
        <div>
          <span className={`font-mono text-xs font-bold ${signalColor(signals.signal_label)}`}>{signals.signal_label}</span>
          <p className="font-mono text-[10px] text-muted-foreground mt-0.5">{signals.name}</p>
        </div>
        <span className={`font-mono text-lg font-black ${signalColor(signals.signal_label)}`}>{signals.composite_score > 0 ? '+' : ''}{signals.composite_score}</span>
      </div>
      <ScoreBar score={signals.composite_score} />
      <div className="mt-3 space-y-0">
        <CategoryScore label="📈 Momentum" data={cats.momentum} />
        <CategoryScore label="💎 Value" data={cats.value} />
        <CategoryScore label="🏆 Quality" data={cats.quality} />
        <CategoryScore label="🧠 Sentiment" data={cats.sentiment} />
        <CategoryScore label="📉 Technical" data={cats.technical} />
      </div>
      <p className="font-mono text-[9px] text-muted-foreground/50 mt-2">Computed {signals.computed_at ? new Date(signals.computed_at).toLocaleTimeString() : 'N/A'}</p>
    </div>
  );
}

// --- Research Memo Stream Component ---
function ResearchMemoPanel({ ticker }) {
  const [streaming, setStreaming] = useState(false);
  const [memoText, setMemoText] = useState('');
  const [agentStatuses, setAgentStatuses] = useState({});
  const [thinking, setThinking] = useState('');
  const [signalData, setSignalData] = useState(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(null);

  const startStream = useCallback(async () => {
    if (!ticker) return;
    setStreaming(true);
    setMemoText('');
    setAgentStatuses({});
    setThinking('');
    setSignalData(null);
    setDone(false);
    setError(null);

    const token = localStorage.getItem('mf_token');
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

    try {
      const response = await fetch(`${API_BASE}/api/research/memo/${ticker}/stream`, { headers, credentials: 'include' });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        setError(errData.detail || 'Failed to start memo stream');
        setStreaming(false);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done: streamDone, value } = await reader.read();
        if (streamDone) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === 'thinking') setThinking(event.message || '');
            else if (event.type === 'token') setMemoText(prev => prev + (event.content || ''));
            else if (event.type === 'agent_complete') {
              setAgentStatuses(prev => ({ ...prev, [event.agent]: 'done' }));
            } else if (event.type === 'signal_scores') {
              setSignalData(event);
            } else if (event.type === 'done') {
              setDone(true);
              setStreaming(false);
              setThinking('');
            }
          } catch { }
        }
      }
    } catch (e) {
      setError(e.message || 'Stream error');
      setStreaming(false);
    }
  }, [ticker]);

  const agentList = ['fundamentals', 'technical', 'macro', 'sentiment', 'risk'];
  const agentIcons = { fundamentals: '📊', technical: '📉', macro: '🌍', sentiment: '🧠', risk: '🛡️' };
  const agentNames = { fundamentals: 'Fundamentals', technical: 'Technical', macro: 'Macro', sentiment: 'Sentiment', risk: 'Risk' };

  return (
    <div>
      {!streaming && !memoText && !done && (
        <div className="text-center py-8">
          <Brain className="w-10 h-10 text-primary mx-auto mb-3 opacity-60" />
          <p className="font-mono text-sm text-muted-foreground mb-4">
            Generate a Goldman Sachs-style research note using 5 specialist AI agents running in parallel.
          </p>
          <Button onClick={startStream} className="font-mono text-xs uppercase tracking-wider bg-primary text-black hover:bg-primary/80">
            <Zap className="w-3.5 h-3.5 mr-2" /> Generate Research Memo
          </Button>
        </div>
      )}

      {streaming && (
        <div className="mb-4">
          {thinking && (
            <div className="flex items-center gap-2 mb-3 text-[#00F3FF] font-mono text-xs animate-pulse">
              <Activity className="w-3.5 h-3.5" />
              <span>{thinking}</span>
            </div>
          )}
          <div className="grid grid-cols-5 gap-1 mb-3">
            {agentList.map(agent => (
              <div key={agent} className={`text-center p-1.5 border rounded-none text-[9px] font-mono transition-colors ${agentStatuses[agent] === 'done' ? 'border-[#00FF41]/40 text-[#00FF41]' : 'border-border/30 text-muted-foreground'}`}>
                <div>{agentIcons[agent]}</div>
                <div>{agentNames[agent]}</div>
                {agentStatuses[agent] === 'done' && <div className="text-[#00FF41]">✓</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {memoText && (
        <div className="relative">
          <div
            className="prose prose-invert max-w-none font-body text-sm leading-relaxed"
            dangerouslySetInnerHTML={{ __html: '<p>' + renderMarkdown(memoText) + '</p>' }}
            style={{ fontSize: '0.8rem', lineHeight: '1.6' }}
          />
          {streaming && <span className="inline-block w-2 h-3.5 bg-primary animate-pulse ml-0.5" />}
        </div>
      )}

      {error && <p className="text-xs text-destructive font-mono mt-2">{error}</p>}

      {done && (
        <div className="mt-4 flex gap-2">
          <Button onClick={startStream} variant="outline" size="sm" className="font-mono text-xs uppercase tracking-wider">
            <RefreshCw className="w-3 h-3 mr-1.5" /> Regenerate
          </Button>
        </div>
      )}
    </div>
  );
}

// --- Ideas Feed Component ---
function IdeasFeed() {
  const [ideas, setIdeas] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/research/ideas')
      .then(({ data }) => setIdeas(data))
      .catch(() => { })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="space-y-2">
      {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
    </div>
  );

  if (!ideas) return <p className="text-xs text-muted-foreground font-mono">Failed to load ideas</p>;

  const { top_buys = [], top_sells = [], anomalies = [], market_conditions = {}, sector_rotation = {}, today_playbook = [] } = ideas;

  return (
    <div className="space-y-4">
      {market_conditions.macro_summary && (
        <div className="p-2.5 border border-[#00F3FF]/20 bg-[#00F3FF]/5">
          <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Macro Context</p>
          <p className="font-mono text-xs text-foreground/80">{market_conditions.macro_summary}</p>
        </div>
      )}

      {sector_rotation.phase && (
        <div className="p-2.5 border border-border/30">
          <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
            Sector Rotation: <span className="text-primary">{sector_rotation.phase}</span>
          </p>
          <p className="font-mono text-[10px] text-foreground/70">{sector_rotation.note}</p>
        </div>
      )}

      {top_buys.length > 0 && (
        <div>
          <p className="font-mono text-[10px] text-[#00FF41] uppercase tracking-wider mb-2">🚀 Top Buy Ideas</p>
          <div className="space-y-1.5">
            {top_buys.map(idea => (
              <button
                key={idea.ticker}
                onClick={() => navigate(`/stock/${idea.ticker}`)}
                className="w-full flex items-center justify-between p-2 border border-[#00FF41]/20 hover:border-[#00FF41]/40 bg-[#00FF41]/5 hover:bg-[#00FF41]/10 transition-colors text-left"
              >
                <div>
                  <span className="font-mono text-xs font-bold text-foreground">{idea.ticker}</span>
                  <span className="font-mono text-[10px] text-muted-foreground ml-2">{idea.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] text-muted-foreground">{idea.sector}</span>
                  <span className="font-mono text-xs text-[#00FF41] font-bold">{idea.score > 0 ? '+' : ''}{idea.score}</span>
                  <ChevronRight className="w-3 h-3 text-muted-foreground" />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {top_sells.length > 0 && (
        <div>
          <p className="font-mono text-[10px] text-[#F85149] uppercase tracking-wider mb-2">📉 Avoid / Short Watch</p>
          <div className="space-y-1.5">
            {top_sells.map(idea => (
              <button
                key={idea.ticker}
                onClick={() => navigate(`/stock/${idea.ticker}`)}
                className="w-full flex items-center justify-between p-2 border border-[#F85149]/20 hover:border-[#F85149]/40 bg-[#F85149]/5 hover:bg-[#F85149]/10 transition-colors text-left"
              >
                <div>
                  <span className="font-mono text-xs font-bold text-foreground">{idea.ticker}</span>
                  <span className="font-mono text-[10px] text-muted-foreground ml-2">{idea.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-[#F85149] font-bold">{idea.score}</span>
                  <ChevronRight className="w-3 h-3 text-muted-foreground" />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {anomalies.length > 0 && (
        <div>
          <p className="font-mono text-[10px] text-[#F0A500] uppercase tracking-wider mb-2">⚡ Market Anomalies</p>
          <div className="space-y-1.5">
            {anomalies.slice(0, 6).map(a => (
              <button
                key={a.ticker}
                onClick={() => navigate(`/stock/${a.ticker}`)}
                className="w-full text-left p-2 border border-[#F0A500]/20 hover:border-[#F0A500]/40 bg-[#F0A500]/5 hover:bg-[#F0A500]/10 transition-colors"
              >
                <div className="flex items-center justify-between mb-0.5">
                  <span className="font-mono text-xs font-bold">{a.ticker}</span>
                  <span className={`font-mono text-[10px] font-bold ${a.change_1d_pct >= 0 ? 'text-[#3FB950]' : 'text-[#F85149]'}`}>
                    {a.change_1d_pct >= 0 ? '+' : ''}{a.change_1d_pct}%
                  </span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {a.anomalies.map((an, i) => (
                    <span key={i} className="font-mono text-[9px] text-[#F0A500] bg-[#F0A500]/10 px-1.5 py-0.5">{an}</span>
                  ))}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {today_playbook.length > 0 && (
        <div className="p-2.5 border border-border/30">
          <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Today's Playbook</p>
          <ul className="space-y-1">
            {today_playbook.map((tip, i) => (
              <li key={i} className="font-mono text-[10px] text-foreground/70 flex gap-2">
                <span className="text-primary">→</span>{tip}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// --- Thematic Research Component ---
function ThematicResearch() {
  const [theme, setTheme] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const PRESET_THEMES = ['AI Infrastructure', 'Clean Energy', 'Big Tech', 'Healthcare Innovation', 'Financials'];

  const runThematic = async (t) => {
    const themeToUse = t || theme;
    if (!themeToUse.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const { data } = await api.post('/research/thematic', { theme: themeToUse });
      setResult(data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to run thematic research');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="flex gap-2 mb-3">
        <Input
          value={theme}
          onChange={e => setTheme(e.target.value)}
          placeholder="e.g. AI infrastructure, clean energy, biotech..."
          className="font-mono text-xs h-8 bg-background border-border/50"
          onKeyDown={e => e.key === 'Enter' && runThematic()}
        />
        <Button
          onClick={() => runThematic()}
          disabled={loading || !theme.trim()}
          size="sm"
          className="font-mono text-xs uppercase tracking-wider bg-primary text-black hover:bg-primary/80 h-8"
        >
          {loading ? <Activity className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
        </Button>
      </div>

      <div className="flex flex-wrap gap-1.5 mb-4">
        {PRESET_THEMES.map(t => (
          <button
            key={t}
            onClick={() => runThematic(t)}
            className="font-mono text-[10px] px-2 py-1 border border-border/30 hover:border-primary/40 hover:text-primary text-muted-foreground transition-colors uppercase tracking-wider"
          >
            {t}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-primary font-mono text-xs animate-pulse py-4">
          <Activity className="w-4 h-4" /> <span>Scanning theme universe and scoring stocks...</span>
        </div>
      )}

      {error && <p className="text-xs text-destructive font-mono">{error}</p>}

      {result && !loading && (
        <div className="space-y-4">
          {result.narrative && (
            <div className="p-3 border border-border/30 bg-muted/10">
              <p className="font-mono text-[10px] text-primary uppercase tracking-wider mb-2">Theme Brief: {result.theme}</p>
              <p className="font-body text-xs text-foreground/80 leading-relaxed">{result.narrative}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            {result.top_longs?.length > 0 && (
              <div>
                <p className="font-mono text-[10px] text-[#00FF41] uppercase tracking-wider mb-2">📈 Long Ideas</p>
                <div className="space-y-1">
                  {result.top_longs.map(s => (
                    <button key={s.symbol} onClick={() => navigate(`/stock/${s.symbol}`)}
                      className="w-full flex items-center justify-between p-1.5 border border-[#00FF41]/20 hover:bg-[#00FF41]/5 text-left transition-colors">
                      <span className="font-mono text-xs font-bold">{s.symbol}</span>
                      <span className={`font-mono text-xs ${signalColor(s.signal_label)}`}>{s.composite_score > 0 ? '+' : ''}{s.composite_score}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {result.top_shorts?.length > 0 && (
              <div>
                <p className="font-mono text-[10px] text-[#F85149] uppercase tracking-wider mb-2">📉 Avoid / Short</p>
                <div className="space-y-1">
                  {result.top_shorts.map(s => (
                    <button key={s.symbol} onClick={() => navigate(`/stock/${s.symbol}`)}
                      className="w-full flex items-center justify-between p-1.5 border border-[#F85149]/20 hover:bg-[#F85149]/5 text-left transition-colors">
                      <span className="font-mono text-xs font-bold">{s.symbol}</span>
                      <span className="font-mono text-xs text-[#F85149]">{s.composite_score}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// --- Main ResearchCenter Page ---
export default function ResearchCenter() {
  const [activeTab, setActiveTab] = useState('ideas');
  const [ticker, setTicker] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const navigate = useNavigate();

  const TABS = [
    { id: 'ideas', label: 'Morning Briefing', icon: Lightbulb },
    { id: 'memo', label: 'Research Memo', icon: BookOpen },
    { id: 'signals', label: 'Quant Signals', icon: BarChart3 },
    { id: 'thematic', label: 'Thematic', icon: FlaskConical },
  ];

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchInput.trim()) {
      const sym = searchInput.toUpperCase().trim();
      setTicker(sym);
      if (activeTab === 'ideas') setActiveTab('memo');
    }
  };

  return (
    <div className="min-h-screen bg-background p-4 md:p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <Brain className="w-7 h-7 text-primary" />
          <div>
            <h1 className="font-mono text-xl font-black tracking-tight text-foreground uppercase">
              Research Center
            </h1>
            <p className="font-mono text-[11px] text-muted-foreground">
              AI-Native Hedge Fund Research • Multi-Agent Analysis • Quantitative Signals
            </p>
          </div>
        </div>

        {/* Ticker Search */}
        <form onSubmit={handleSearch} className="flex gap-2 mt-3 max-w-sm">
          <Input
            value={searchInput}
            onChange={e => setSearchInput(e.target.value.toUpperCase())}
            placeholder="Enter ticker (e.g. NVDA)..."
            className="font-mono text-xs h-8 bg-background border-border/50"
          />
          <Button type="submit" size="sm" className="font-mono text-xs uppercase h-8 bg-primary text-black hover:bg-primary/80">
            <Search className="w-3.5 h-3.5 mr-1.5" /> Analyze
          </Button>
        </form>

        {ticker && (
          <div className="flex items-center gap-2 mt-2">
            <Badge variant="outline" className="font-mono text-[10px] text-primary border-primary/30">
              <Target className="w-3 h-3 mr-1" /> Active: {ticker}
            </Badge>
            <button onClick={() => setTicker('')} className="font-mono text-[10px] text-muted-foreground hover:text-foreground">clear</button>
          </div>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 mb-6 border-b border-border/30">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 px-3 py-2 font-mono text-xs uppercase tracking-wider transition-colors border-b-2 -mb-px ${activeTab === id
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'}`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Main Content */}
        <div className="lg:col-span-2">
          <Card className="border-border/50 bg-card">
            <CardHeader className="pb-3 border-b border-border/30">
              <CardTitle className="font-mono text-sm uppercase tracking-wider text-foreground flex items-center gap-2">
                {TABS.find(t => t.id === activeTab)?.icon && (() => {
                  const Icon = TABS.find(t => t.id === activeTab).icon;
                  return <Icon className="w-4 h-4 text-primary" />;
                })()}
                {TABS.find(t => t.id === activeTab)?.label}
                {ticker && activeTab !== 'ideas' && activeTab !== 'thematic' && (
                  <Badge variant="outline" className="font-mono text-[10px] border-primary/30 text-primary ml-1">{ticker}</Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              {activeTab === 'ideas' && <IdeasFeed />}
              {activeTab === 'memo' && (
                ticker
                  ? <ResearchMemoPanel ticker={ticker} />
                  : <div className="text-center py-8 text-muted-foreground font-mono text-sm">
                    Enter a ticker above to generate a research memo
                  </div>
              )}
              {activeTab === 'signals' && (
                ticker
                  ? <SignalPanel ticker={ticker} />
                  : <div className="text-center py-8 text-muted-foreground font-mono text-sm">
                    Enter a ticker above to view quantitative signals
                  </div>
              )}
              {activeTab === 'thematic' && <ThematicResearch />}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Signal summary (always show if ticker active) */}
          {ticker && (
            <Card className="border-border/50 bg-card">
              <CardHeader className="pb-2 border-b border-border/30">
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                  <BarChart3 className="w-3.5 h-3.5 text-primary" /> Quant Signals — {ticker}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-3">
                <SignalPanel ticker={ticker} />
              </CardContent>
            </Card>
          )}

          {/* Quick navigate */}
          <Card className="border-border/50 bg-card">
            <CardHeader className="pb-2 border-b border-border/30">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                <Zap className="w-3.5 h-3.5 text-primary" /> Quick Actions
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-3 space-y-1.5">
              {[
                { label: 'Macro Dashboard', path: '/macro', icon: Activity, color: '#00F3FF' },
                { label: 'Risk Console', path: '/risk', icon: Shield, color: '#F0A500' },
                { label: 'AI Screener', path: '/screener', icon: Search, color: '#00FF41' },
                { label: 'News Feed', path: '/news', icon: Star, color: '#F0A500' },
              ].map(({ label, path, icon: Icon, color }) => (
                <button
                  key={path}
                  onClick={() => navigate(path)}
                  className="w-full flex items-center justify-between p-2 border border-border/30 hover:border-border/60 hover:bg-muted/10 transition-colors text-left"
                >
                  <div className="flex items-center gap-2">
                    <Icon className="w-3.5 h-3.5" style={{ color }} />
                    <span className="font-mono text-xs text-foreground/80">{label}</span>
                  </div>
                  <ChevronRight className="w-3 h-3 text-muted-foreground" />
                </button>
              ))}
            </CardContent>
          </Card>

          {/* Hot tickers */}
          <Card className="border-border/50 bg-card">
            <CardHeader className="pb-2 border-b border-border/30">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-primary" /> Quick Analyze
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-3">
              <div className="flex flex-wrap gap-1.5">
                {['AAPL', 'NVDA', 'MSFT', 'TSLA', 'AMZN', 'META', 'GOOGL', 'AMD'].map(t => (
                  <button
                    key={t}
                    onClick={() => { setTicker(t); setSearchInput(t); setActiveTab('memo'); }}
                    className="font-mono text-[10px] px-2 py-1 border border-border/30 hover:border-primary/40 hover:text-primary text-muted-foreground transition-colors"
                  >
                    {t}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
