import { useState, useRef, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { MessageSquare, X, Send, Zap, Lock, Loader2, Plus, History, ChevronLeft, ChevronDown, ChevronRight, Paperclip, TerminalSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import api, { API_BASE } from '@/lib/api';

const CUSTOM_STYLES = `
  .terminal-scrollbar::-webkit-scrollbar { width: 4px; }
  .terminal-scrollbar::-webkit-scrollbar-track { background: transparent; }
  .terminal-scrollbar::-webkit-scrollbar-thumb { background: rgba(0, 255, 136, 0.3); border-radius: 4px; }
  .terminal-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(0, 255, 136, 0.6); }
  
  .terminal-pulse {
    box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.4);
    animation: pulse-green 2s infinite;
  }
  @keyframes pulse-green {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.8); }
    70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(0, 255, 136, 0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0); }
  }

  .eq-bar { animation: eq-bounce 1.2s ease-in-out infinite; background: #00ff88; width: 3px; border-radius: 2px; }
  .eq-bar:nth-child(1) { animation-delay: 0.0s; }
  .eq-bar:nth-child(2) { animation-delay: 0.2s; }
  .eq-bar:nth-child(3) { animation-delay: 0.4s; }
  @keyframes eq-bounce {
    0%, 100% { height: 6px; }
    50% { height: 16px; }
  }

  .fin-card {
    background: var(--card-bg, rgba(255, 255, 255, 0.03));
    border-left: 3px solid #00ff88;
    padding: 10px 14px;
    margin: 6px 0;
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  }
  .dark .fin-card {
    background: rgba(255, 255, 255, 0.03);
  }
  .fin-card-header { display: flex; justify-content: space-between; align-items: center; }
  .fin-card-title { font-weight: 600; color: inherit; }
  .fin-card-value { color: var(--color-accent); font-weight: 700; font-size: 15px; }
  .dark .fin-card-value { color: var(--color-accent); }
  .fin-impact-badge {
    background: rgba(0, 255, 136, 0.15);
    color: var(--color-accent);
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
    display: inline-block;
    margin-right: 6px;
  }
  .dark .fin-impact-badge { color: var(--color-accent); }
  .fin-impact-text { font-size: 12px; line-height: 1.5; opacity: 0.8; }
`;

function renderMarkdown(text) {
  if (!text) return '';
  
  // 1. Handle specialized financial cards first
  let html = text
    .replace(/(?:^|\n)[-*]\s+\**([^*:]+?)\**:\s*(.*?)(?:\n\s*Market Impact:\s*(.*?))?(?=\n|$)/gmi, (match, title, value, impact) => {
      let card = `<div class="fin-card">
        <div class="fin-card-header">
          <span class="fin-card-title">${title.trim()}</span>
          <span class="fin-card-value">${value.trim().replace(/\*\*/g, '')}</span>
        </div>`;
      if (impact) {
        card += `<div><span class="fin-impact-badge">Market Impact:</span><span class="fin-impact-text">${impact.trim()}</span></div>`;
      }
      card += `</div>`;
      return card;
    });

  // 2. Handle Tables
  const lines = html.split('\n');
  let inTable = false;
  let tableHtml = '';
  let processedLines = [];

  for (let line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      const cells = trimmed.split('|').filter((_, i, arr) => i > 0 && i < arr.length - 1);
      if (!inTable) {
        inTable = true;
        tableHtml = '<div class="w-full overflow-x-auto my-3"><table class="w-full text-[11px] text-left border-collapse border border-primary/20 bg-primary/5 rounded-md overflow-hidden">';
        tableHtml += '<thead class="bg-primary/10 font-mono uppercase tracking-wider text-[10px] opacity-80 border-b border-primary/20">';
        tableHtml += '<tr>' + cells.map(c => `<th class="px-2 py-1.5 border-r border-primary/10 last:border-r-0">${c.trim()}</th>`).join('') + '</tr></thead>';
        tableHtml += '<tbody class="divide-y divide-primary/10">';
      } else if (trimmed.includes('---')) {
        continue; // Skip separator line
      } else {
        tableHtml += '<tr class="hover:bg-primary/5 transition-colors">' + cells.map(c => `<td class="px-2 py-1.5 border-r border-primary/10 last:border-r-0">${c.trim()}</td>`).join('') + '</tr>';
      }
    } else {
      if (inTable) {
        tableHtml += '</tbody></table></div>';
        processedLines.push(tableHtml);
        tableHtml = '';
        inTable = false;
      }
      processedLines.push(line);
    }
  }
  if (inTable) {
    tableHtml += '</tbody></table></div>';
    processedLines.push(tableHtml);
  }
  
  html = processedLines.join('\n');

  // 3. Handle Typography
  return html
    .replace(/^### (.*$)/gm, '<h3 style="color: var(--color-accent, #00ff88); font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 20px; margin-bottom: 8px;">$1</h3>')
    .replace(/^## (.*$)/gm, '<h2 style="color: #ffffff; font-size: 15px; font-weight: 700; border-left: 3px solid var(--color-accent); padding-left: 8px; margin-top: 24px; margin-bottom: 10px;">$1</h2>')
    .replace(/^# (.*$)/gm, '<h1 style="color: #ffffff; font-size: 18px; font-weight: 800; margin-top: 28px; margin-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px;">$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong style="color: #ffffff; font-weight: 700;">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em style="opacity: 0.9;">$1</em>')
    .replace(/`([^`]+)`/g, '<code class="bg-muted text-primary px-1.5 py-0.5 rounded font-mono text-[11px] border border-primary/20 mx-0.5">$1</code>')
    .replace(/^(?:-|\*)\s+(?!<div)(.*$)/gm, '<div style="color: rgba(255,255,255,0.85); margin-left: 14px; text-indent: -14px; margin-bottom: 4px;">&bull; $1</div>')
    .replace(/\n\n/g, '</p><p class="mt-3 opacity-90 leading-relaxed">')
    .replace(/\n(?!\s*<)/g, '<br/>'); // Only add <br/> if not followed by a tag
}


function CollapsibleMarkdown({ content, isError, streaming }) {
  const [expanded, setExpanded] = useState(false);

  // Only truncate if not streaming, otherwise the user sees a jarring cut during generation
  const words = content.split(/\s+/);
  const isLong = !streaming && words.length > 400;

  const displayText = (!isLong || expanded) ? content : words.slice(0, 200).join(' ') + '...';

  return (
    <div className="relative w-full">
      <div
        className={`markdown-content text-xs leading-relaxed ${isError ? 'text-destructive' : ''}`}
        dangerouslySetInnerHTML={{ __html: renderMarkdown(displayText) || '' }}
      />
      {streaming && <span className="inline-block w-1.5 h-3 bg-primary ml-1 animate-pulse" />}

      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-3 dark:text-[#00ff88] text-[#059669] text-[11px] hover:underline cursor-pointer font-sans transition-colors block"
        >
          {expanded ? 'Show less ▴' : 'Show full analysis ▾'}
        </button>
      )}
    </div>
  );
}

function ThinkingAccordion({ steps, isProcessing }) {
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    // Auto-expand while processing, auto-collapse when done
    if (isProcessing) setExpanded(true);
    else setExpanded(false);
  }, [isProcessing]);

  if (!steps || steps.length === 0) return null;

  return (
    <div className="mb-3 border border-primary/20 rounded-md bg-primary/5 overflow-hidden shadow-sm">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 bg-primary/5 hover:bg-primary/10 transition-colors"
      >
        <div className="flex items-center gap-2">
          {isProcessing ? (
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
          ) : (
            <span className="text-primary font-bold text-xs">✓</span>
          )}
          <span className={`text-[11px] font-mono tracking-wide ${isProcessing ? 'text-foreground font-semibold' : 'text-muted-foreground'}`}>
            {isProcessing ? '⚡ Analyzing Markets...' : 'Analysis Complete'}
          </span>
        </div>
        {expanded ? <ChevronDown className="w-3 h-3 text-muted-foreground" /> : <ChevronRight className="w-3 h-3 text-muted-foreground" />}
      </button>

      {expanded && (
        <div className="px-3 py-2 space-y-2 border-t border-primary/10">
          {steps.map((step, i) => (
            <div
              key={step.id || i}
              className="flex items-start gap-2 text-[11px] font-mono"
              style={{ animation: `fadeIn 150ms ease-out ${i * 150}ms both` }}
            >
              <span className={`mt-0.5 ${!isProcessing && i === steps.length - 1 ? 'text-primary' : 'text-muted-foreground'}`}>
                [✓]
              </span>
              <span className={!isProcessing || i < steps.length - 1 ? 'text-muted-foreground' : 'text-primary'}>
                {step.message}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AIChatbot({ isChatOpen, setIsChatOpen, chatWidth, setChatWidth, isDesktop }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [aiUsage, setAiUsage] = useState({ remaining: 3, unlimited: false });
  const [isResizing, setIsResizing] = useState(false);
  const [thinkingSteps, setThinkingSteps] = useState([]);
  const [followUpQuestions, setFollowUpQuestions] = useState([]);
  const [showSourcesModal, setShowSourcesModal] = useState(false);
  const [selectedSources, setSelectedSources] = useState(null);
  const scrollRef = useRef(null);
  const textareaRef = useRef(null);
  const location = useLocation();
  const { user } = useAuth();
  const sessionId = useRef(`chat_${Date.now()}`);

  // Chat history
  const [chatHistory, setChatHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // Load chat history from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('mf_chat_history');
      if (saved) setChatHistory(JSON.parse(saved));
    } catch { }
  }, []);

  // Save chat history
  const saveToChatHistory = useCallback((msgs, sid) => {
    if (msgs.length === 0) return;
    const firstUserMsg = msgs.find(m => m.role === 'user');
    const title = firstUserMsg?.content?.slice(0, 50) || 'New Chat';
    setChatHistory(prev => {
      const existing = prev.findIndex(h => h.id === sid);
      let updated;
      if (existing >= 0) {
        updated = [...prev];
        updated[existing] = { ...updated[existing], messages: msgs, title, updatedAt: Date.now() };
      } else {
        updated = [{ id: sid, messages: msgs, title, updatedAt: Date.now() }, ...prev].slice(0, 20);
      }
      try { localStorage.setItem('mf_chat_history', JSON.stringify(updated)); } catch { }
      return updated;
    });
  }, []);

  useEffect(() => {
    api.get('/ai/usage').then(res => setAiUsage(res.data)).catch(() => { });
  }, [user]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, thinkingSteps, followUpQuestions]);

  useEffect(() => {
    if (!isResizing) return;
    const handleMouseMove = (e) => {
      const newWidth = window.innerWidth - e.clientX;
      if (newWidth > 300 && newWidth < window.innerWidth * 0.5) {
        setChatWidth(newWidth);
      }
    };
    const handleMouseUp = () => setIsResizing(false);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.classList.add('select-none');
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.classList.remove('select-none');
    };
  }, [isResizing, setChatWidth]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  }, [input]);

  const getContext = () => {
    const path = location.pathname;
    if (path.startsWith('/stock/')) return `User is viewing stock details for ${path.split('/stock/')[1]}`;
    if (path === '/news') return 'User is on the news feed page';
    if (path === '/screener') return 'User is on the AI stock screener page';
    if (path === '/portfolio') return 'User is on the portfolio page';
    return 'User is on the dashboard';
  };

  const getSuggestionChips = useCallback(() => {
    let ticker = null;
    const path = location.pathname;
    if (path.startsWith('/stock/')) {
      ticker = path.split('/stock/')[1]?.toUpperCase() || null;
    }

    if (ticker) {
      return [
        `Analyze ${ticker} stock`,
        `Technical outlook for ${ticker}`,
        `Recent insider activity for ${ticker}`,
      ];
    }
    return [
      'What is driving the market today?',
      'Which sectors are outperforming right now?',
      "Summarize today's macro environment",
    ];
  }, [location.pathname]);

  const startNewChat = () => {
    // Save current conversation
    if (messages.length > 0) {
      saveToChatHistory(messages, sessionId.current);
    }
    setMessages([]);
    setInput('');
    setFollowUpQuestions([]);
    setThinkingSteps([]);
    sessionId.current = `chat_${Date.now()}`;
    setShowHistory(false);
  };

  const loadChat = (chat) => {
    // Save current first
    if (messages.length > 0) {
      saveToChatHistory(messages, sessionId.current);
    }
    setMessages(chat.messages || []);
    sessionId.current = chat.id;
    setFollowUpQuestions([]);
    setThinkingSteps([]);
    setShowHistory(false);
  };

  const getCurrentTicker = () => {
    const path = location.pathname;
    if (path.startsWith('/stock/')) {
      return path.split('/stock/')[1]?.toUpperCase() || null;
    }
    return null;
  };

  // Fetch follow-up questions after a response
  const fetchFollowUps = async (lastResponse) => {
    try {
      const res = await api.post('/ai/follow-up', {
        last_response: lastResponse,
        context: getContext(),
        topic: getCurrentTicker() || 'finance',
      });
      if (res.data.questions?.length > 0) {
        setFollowUpQuestions(res.data.questions);
      }
    } catch {
      // Silent fail
    }
  };

  const sendMessage = async (overrideInput) => {
    const messageText = overrideInput || input;
    if (!messageText.trim() || loading) return;
    if (!aiUsage.unlimited && aiUsage.remaining <= 0) return;

    const userMsg = { role: 'user', content: messageText };
    setMessages(prev => [...prev, userMsg]);
    const sentInput = messageText;
    setInput('');
    setFollowUpQuestions([]);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setLoading(true);
    setThinkingSteps([]);

    try {
      let detectedTicker = getCurrentTicker();
      const tickerMatch = sentInput.toUpperCase().match(/\b([A-Z]{1,5})\b/);
      if (tickerMatch && ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'JPM', 'V', 'WMT', 'JNJ', 'XOM', 'AMD', 'INTC', 'NFLX', 'DIS', 'BA', 'GS', 'PFE', 'KO'].includes(tickerMatch[1])) {
        detectedTicker = tickerMatch[1];
      }

      const token = localStorage.getItem('mf_token');
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers.Authorization = `Bearer ${token}`;

      const res = await fetch(`${API_BASE}/api/ai/chat/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: sentInput,
          session_id: sessionId.current,
          context: getContext(),
          ticker: detectedTicker,
        }),
      });

      if (!res.ok) {
        if (res.status === 429) throw new Error('429');
        throw new Error('Failed');
      }

      if (!aiUsage.unlimited) {
        setAiUsage(prev => ({ ...prev, remaining: Math.max(0, prev.remaining - 1) }));
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let responseContent = '';
      let assistantMsgAdded = false;
      let buffer = '';
      let currentThinkingSteps = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;
          try {
            const jsonStr = trimmed.slice(6);
            const event = JSON.parse(jsonStr);

            if (event.type === 'thinking') {
              const newStep = { step: event.step, message: event.message, id: Date.now() };
              currentThinkingSteps = [...currentThinkingSteps, newStep];
              setThinkingSteps(currentThinkingSteps);

              // If we already started the assistant message, update its thinking array
              if (assistantMsgAdded) {
                setMessages(prev => {
                  const n = [...prev];
                  n[n.length - 1] = { ...n[n.length - 1], thinking: currentThinkingSteps };
                  return n;
                });
              }
            } else if (event.type === 'token') {
              if (!assistantMsgAdded) {
                assistantMsgAdded = true;
                setMessages(prev => [...prev, {
                  role: 'assistant',
                  content: '',
                  streaming: true,
                  thinking: currentThinkingSteps
                }]);
                // We keep currentThinkingSteps around, just in case more thinking events come (unlikely but possible)
              }
              responseContent += event.content;
              const snap = responseContent;
              const now = new Date();
              setMessages(prev => {
                const n = [...prev];
                if (n.length > 0) {
                  n[n.length - 1] = {
                    ...n[n.length - 1],
                    content: snap,
                    streaming: true,
                    timestamp: now
                  };
                }
                return n;
              });
            } else if (event.type === 'done') {
              if (assistantMsgAdded) {
                const final = responseContent;
                const now = new Date();
                setMessages(prev => {
                  const n = [...prev];
                  if (n.length > 0) {
                    n[n.length - 1] = {
                      ...n[n.length - 1],
                      content: final,
                      streaming: false,
                      timestamp: now,
                      sources: ['Market APIs']
                    };
                  }
                  return n;
                });
              }
              setThinkingSteps([]);
            }
          } catch { }
        }
      }

      if (!assistantMsgAdded && responseContent) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: responseContent,
          timestamp: new Date(),
          sources: ['Market APIs'],
          thinking: currentThinkingSteps
        }]);
      } else if (!assistantMsgAdded) {
        setMessages(prev => [...prev, { role: 'assistant', content: 'No response received. Please try again.' }]);
      }

      // Save + fetch follow-ups
      const allMsgs = [...messages, userMsg, { role: 'assistant', content: responseContent || '' }];
      saveToChatHistory(allMsgs, sessionId.current);
      if (responseContent) fetchFollowUps(responseContent);

    } catch (err) {
      if (err.name === 'AbortError') {
        console.log('Fetch aborted');
      } else {
        console.error("Chat error:", err);

        let errorMessage = "Something went wrong. Please try again.";
        if (err.message === '429') {
          errorMessage = "AI usage limit reached. Please sign in for unlimited access.";
        }

        setMessages(prev => [...prev, { role: 'assistant', content: errorMessage, isError: true }]);
        setThinkingSteps([]);
      }
    } finally {
      setLoading(false);
      saveToChatHistory(messages, sessionId.current);
    }
  };

  return (
    <>
      <style>{CUSTOM_STYLES}</style>

      {/* Floating button */}
      {!isChatOpen && (
        <button
          data-testid="chatbot-toggle"
          onClick={() => setIsChatOpen(true)}
          className="fixed bottom-6 right-6 z-[999] group flex items-center justify-center gap-2 px-5 py-3.5 bg-gradient-to-tr from-primary to-[#00d035] text-primary-foreground font-semibold rounded-full shadow-lg hover:shadow-primary/30 hover:scale-105 transition-all duration-300"
        >
          <TerminalSquare className="w-5 h-5 fill-black/10" />
          <span className="text-sm hidden sm:inline">Flux AI</span>
        </button>
      )}

      {/* Chat window */}
      {isChatOpen && (
        <div
          data-testid="chatbot-window"
          className={`fixed z-[999] flex flex-col overflow-hidden transition-transform duration-300 ease-in-out dark:bg-[#0a0a0f] bg-slate-50 dark:border-primary/15 border-border ${isDesktop
            ? 'top-0 right-0 bottom-0 h-full border-l shadow-2xl'
            : 'bottom-6 right-6 w-[380px] h-[580px] max-h-[85vh] rounded-[12px] shadow-[0_0_40px_rgba(0,255,136,0.05)] border-t border-l border-r'
            }`}
          style={{
            width: isDesktop ? `${chatWidth}px` : '380px',
            transform: isDesktop ? `translateX(${isChatOpen ? 0 : '100%'})` : 'none'
          }}
        >
          {/* Resize Handle */}
          {isDesktop && (
            <div
              className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-primary/50 transition-colors z-50 group"
              onMouseDown={(e) => { e.preventDefault(); setIsResizing(true); }}
            >
              <div className="absolute left-0.5 top-1/2 -translate-y-1/2 h-8 w-0.5 bg-border group-hover:bg-primary rounded-full transition-colors" />
            </div>
          )}

          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b dark:border-primary/15 border-border dark:bg-gradient-to-b dark:from-[#0d1117] dark:to-[#0a0a0f] dark:bg-muted/30 bg-muted">
            <div className="flex items-center gap-2">
              {showHistory && (
                <button onClick={() => setShowHistory(false)} className="mr-1">
                  <ChevronLeft className="w-4 h-4 text-muted-foreground hover:text-foreground" />
                </button>
              )}
              <span className="w-2.5 h-2.5 rounded-full bg-primary terminal-pulse" />
              <span className="font-mono text-sm font-bold text-foreground uppercase tracking-widest ml-1">
                {showHistory ? 'History' : 'FLUX AI'}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                data-testid="new-chat-btn"
                onClick={startNewChat}
                className="p-1.5 text-muted-foreground hover:text-primary transition-colors"
                title="New Chat"
              >
                <Plus className="w-4 h-4" />
              </button>
              <button
                data-testid="chat-history-btn"
                onClick={() => setShowHistory(!showHistory)}
                className={`p-1.5 transition-colors ${showHistory ? 'text-primary' : 'text-muted-foreground hover:text-foreground'}`}
                title="Chat History"
              >
                <History className="w-4 h-4" />
              </button>
              {!aiUsage.unlimited && (
                <span className="text-[10px] font-mono text-muted-foreground ml-1">
                  {aiUsage.remaining}/3
                </span>
              )}
              <button data-testid="chatbot-close" onClick={() => setIsChatOpen(false)} className="ml-1">
                <X className="w-4 h-4 text-muted-foreground hover:text-foreground" />
              </button>
            </div>
          </div>

          {/* History View */}
          {showHistory ? (
            <div className="flex-1 overflow-y-auto p-3 space-y-1 terminal-scrollbar">
              {chatHistory.length === 0 ? (
                <p className="text-xs font-mono text-muted-foreground text-center py-8">No chat history yet</p>
              ) : (
                chatHistory.map((chat) => (
                  <button
                    key={chat.id}
                    onClick={() => loadChat(chat)}
                    className={`w-full text-left px-3 py-2.5 border transition-colors text-xs font-mono truncate ${chat.id === sessionId.current
                      ? 'border-primary/30 bg-primary/5 text-primary'
                      : 'border-border text-muted-foreground hover:border-primary/30 hover:text-foreground'
                      }`}
                  >
                    <span className="block truncate">{chat.title}</span>
                    <span className="text-[9px] text-muted-foreground/60 mt-0.5 block">
                      {new Date(chat.updatedAt).toLocaleDateString()} · {chat.messages?.length || 0} msgs
                    </span>
                  </button>
                ))
              )}
            </div>
          ) : (
            <>
              {/* Messages */}
              <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-4 terminal-scrollbar relative">
                {messages.length === 0 && (
                  <div className="text-center py-8">
                    <span className="inline-block w-4 h-4 rounded-full bg-primary/30 terminal-pulse mb-3" />
                    <p className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
                      Ask me about markets, stocks, or investing
                    </p>
                    <div className="mt-4 space-y-2">
                      {getSuggestionChips().map(q => (
                        <button
                          key={q}
                          data-testid={`quick-question-${q.slice(0, 10).replace(/\\s/g, '-')}`}
                          onClick={() => { setInput(q); }}
                          className="block w-full text-left text-xs px-3 py-2 border border-border text-muted-foreground hover:border-primary/50 hover:bg-primary/5 hover:text-primary transition-colors font-mono rounded-md"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {messages.map((msg, i) => (
                  <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                    <div
                      className={`px-3 py-2 text-sm ${msg.role === 'user'
                        ? 'bg-[rgba(99,102,241,0.15)] dark:bg-[rgba(99,102,241,0.2)] border border-[rgba(99,102,241,0.3)] dark:border-[rgba(99,102,241,0.4)] text-foreground dark:text-[#e0e0e0] rounded-[12px_12px_2px_12px] text-[13px] ml-auto max-w-[80%] shadow-sm'
                        : 'text-foreground max-w-[95%] w-full'
                        }`}
                    >
                      {msg.role === 'assistant' ? (
                        <div className="flex flex-col w-full">
                          {/* Render Thinking Accordion inside the message if it exists */}
                          {msg.thinking && msg.thinking.length > 0 && (
                            <ThinkingAccordion
                              steps={msg.thinking}
                              isProcessing={msg.streaming || (i === messages.length - 1 && loading)}
                            />
                          )}

                          <CollapsibleMarkdown content={msg.content} isError={msg.isError} streaming={msg.streaming} />

                          {/* Metadata Row */}
                          {!msg.streaming && msg.timestamp && (
                            <div className="flex items-center justify-between mt-3 pt-2 border-t dark:border-border/50 border-border">
                              <div className="flex items-center gap-2 mt-2 font-mono text-[9px] text-muted-foreground/50 uppercase tracking-widest pl-10 border-t border-border/10 pt-2">
                                {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </div>
                              {msg.sources && (
                                <button
                                  onClick={() => {
                                    setSelectedSources({ sources: msg.sources, thinking: msg.thinking });
                                    setShowSourcesModal(true);
                                  }}
                                  className="flex items-center gap-1 text-[10px] text-primary/70 hover:text-primary font-mono transition-colors"
                                >
                                  <Paperclip className="w-3 h-3" />
                                  Aggregated Data
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="font-mono text-[13px]">{msg.content}</span>
                      )}
                    </div>
                  </div>
                ))}

                {/* Loading State (Before first token arrives, show floating thinking steps) 
                    Only show if we haven't created the assistant message yet */}
                {loading && thinkingSteps.length > 0 && messages[messages.length - 1]?.role === 'user' && (
                  <div className="flex justify-start max-w-[95%]">
                    <div className="w-full">
                      <ThinkingAccordion steps={thinkingSteps} isProcessing={true} />
                    </div>
                  </div>
                )}

                {loading && thinkingSteps.length === 0 && (
                  <div className="flex items-center gap-3 px-2 py-3">
                    <div className="flex items-end gap-[3px] h-4">
                      <div className="eq-bar h-2" />
                      <div className="eq-bar h-4" />
                      <div className="eq-bar h-2" />
                    </div>
                    <span className="text-[11px] font-mono text-muted-foreground">Querying live market data...</span>
                  </div>
                )}

                {/* Follow-up Questions */}
                {followUpQuestions.length > 0 && !loading && messages.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    <span className="text-[9px] font-mono text-muted-foreground uppercase tracking-wider">Follow up:</span>
                    {followUpQuestions.map((q, i) => (
                      <button
                        key={i}
                        data-testid={`follow-up-${i}`}
                        onClick={() => sendMessage(q)}
                        className="block w-full text-left text-[11px] px-3 py-2 border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors font-sans rounded"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Rate limit warning */}
              {!aiUsage.unlimited && aiUsage.remaining <= 0 && (
                <div className="px-3 py-2 bg-destructive/10 border-t border-destructive/30 flex items-center gap-2">
                  <Lock className="w-3 h-3 text-destructive" />
                  <span className="text-[10px] font-mono text-destructive">Login for unlimited AI access</span>
                </div>
              )}

              {/* Input */}
              <div
                className="p-3 border-t dark:border-primary/15 border-border dark:bg-gradient-to-t dark:from-[#0d1117] dark:to-[#0a0a0f] dark:bg-muted/20 bg-muted"
              >
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (input.trim() && !loading && (aiUsage.unlimited || aiUsage.remaining > 0)) {
                      sendMessage();
                    }
                  }}
                  className="flex items-end gap-2"
                >
                  <div className="relative flex-1 flex items-end">
                    <textarea
                      ref={textareaRef}
                      data-testid="chatbot-input"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          if (input.trim() && !loading && (aiUsage.unlimited || aiUsage.remaining > 0)) {
                            sendMessage();
                          }
                        }
                      }}
                      placeholder="Ask about markets, stocks, macro..."
                      className="flex-1 w-full dark:bg-[rgba(255,255,255,0.04)] bg-slate-100 text-foreground dark:border-[rgba(255,255,255,0.1)] border-border focus:border-primary/50 focus:ring-0 focus:shadow-[0_0_0_2px_rgba(0,255,136,0.1)] rounded-md font-mono text-xs px-3 py-2.5 min-h-[40px] resize-none terminal-scrollbar placeholder:text-muted-foreground/50 pr-8"
                      rows={1}
                      disabled={loading || (!aiUsage.unlimited && aiUsage.remaining <= 0)}
                    />
                    <span className="absolute right-3 top-[50%] -translate-y-[50%] text-muted-foreground/50 pointer-events-none text-xs hidden sm:block">⏎</span>
                  </div>
                  <Button
                    data-testid="chatbot-send"
                    type="submit"
                    size="sm"
                    disabled={loading || !input.trim()}
                    className="rounded-md bg-primary text-primary-foreground hover:bg-primary/90 hover:scale-105 transition-transform px-3 h-[40px] shadow-sm ml-1"
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </form>
              </div>
            </>
          )}
        </div>
      )}

      {/* Sources Modal */}
      {showSourcesModal && selectedSources && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-background border border-border rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between p-4 border-b border-border bg-muted/30">
              <div className="flex items-center gap-2">
                <Paperclip className="w-4 h-4 text-primary" />
                <h3 className="font-semibold text-sm">Aggregated Data Sources</h3>
              </div>
              <button 
                onClick={() => setShowSourcesModal(false)}
                className="text-muted-foreground hover:text-foreground transition-colors p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 max-h-[60vh] overflow-y-auto terminal-scrollbar">
              <div className="space-y-4">
                <div>
                  <h4 className="text-xs font-mono text-muted-foreground uppercase tracking-wider mb-2">Sources</h4>
                  <ul className="space-y-1.5">
                    {selectedSources.sources.map((src, idx) => (
                      <li key={idx} className="text-sm flex items-start gap-2">
                        <span className="text-primary mt-1">•</span>
                        <span>{src}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                
                {selectedSources.thinking && selectedSources.thinking.length > 0 && (
                   <div>
                     <h4 className="text-xs font-mono text-muted-foreground uppercase tracking-wider mb-2 mt-4">Analysis Pipeline</h4>
                     <div className="space-y-2 bg-muted/20 p-3 rounded-lg border border-border/50">
                       {selectedSources.thinking.map((step, idx) => (
                         <div key={idx} className="flex items-start gap-2 text-xs font-mono">
                           <span className="text-primary mt-0.5">[✓]</span>
                           <span className="text-muted-foreground">{step.message}</span>
                         </div>
                       ))}
                     </div>
                   </div>
                )}
              </div>
            </div>
            <div className="p-3 border-t border-border bg-muted/30 flex justify-end">
              <Button size="sm" variant="outline" onClick={() => setShowSourcesModal(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
