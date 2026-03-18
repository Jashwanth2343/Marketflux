import os

FILE_PATH = "src/components/AIChatbot.js"

with open(FILE_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update imports
content = content.replace(
    "import { MessageSquare, X, Send, Zap, Lock, Loader2, Plus, History, ChevronLeft } from 'lucide-react';",
    "import { MessageSquare, X, Send, Zap, Lock, Loader2, Plus, History, ChevronLeft, ChevronDown, ChevronRight, Paperclip } from 'lucide-react';"
)

# 2. Add custom styles
custom_styles = """
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
    background: rgba(255, 255, 255, 0.03);
    border-left: 3px solid #00ff88;
    padding: 10px 14px;
    margin: 6px 0;
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .fin-card-header { display: flex; justify-content: space-between; align-items: center; }
  .fin-card-title { color: #e8e8e8; font-weight: 600; }
  .fin-card-value { color: #00ff88; font-weight: 700; font-size: 15px; }
  .fin-impact-badge {
    background: rgba(0, 255, 136, 0.15);
    color: #00ff88;
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
    display: inline-block;
    margin-right: 6px;
  }
  .fin-impact-text { color: #aaa; font-size: 12px; line-height: 1.5; }
`;
"""

if "CUSTOM_STYLES =" not in content:
    content = content.replace("function renderMarkdown(text) {", custom_styles + "\nfunction renderMarkdown(text) {")

# 3. Enhance Render Markdown with Financial Cards
render_md_old = """function renderMarkdown(text) {
  if (!text) return '';
  let html = text
    .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
    .replace(/\\*(.*?)\\*/g, '<em>$1</em>')
    .replace(/^### (.*$)/gm, '<h3 class="text-white mt-3 mb-1 font-bold text-sm">$1</h3>')
    .replace(/^## (.*$)/gm, '<h2 class="text-white mt-3 mb-1 font-bold text-base">$1</h2>')
    .replace(/^# (.*$)/gm, '<h1 class="text-white mt-4 mb-2 font-bold text-lg">$1</h1>')
    .replace(/^\\- (.*$)/gm, '<li class="ml-4 list-disc">$1</li>')
    .replace(/^\\* (.*$)/gm, '<li class="ml-4 list-disc">$1</li>')
    .replace(/`([^`]+)`/g, '<code class="bg-gray-800 text-[#FFB000] px-1 rounded">$1</code>')
    .replace(/\\n\\n/g, '</p><p class="mt-2">')
    .replace(/\\n/g, '<br/>');"""
    
render_md_new = """function renderMarkdown(text) {
  if (!text) return '';
  let html = text
    .replace(/(?:^|\\n)[-*]\\s+\\**([^*:]+?)\\**:\\s*(.*?)(?:\\n\\s*Market Impact:\\s*(.*?))?(?=\\n|$)/gmi, (match, title, value, impact) => {
      let card = `<div class="fin-card">
        <div class="fin-card-header">
          <span class="fin-card-title">${title.trim()}</span>
          <span class="fin-card-value">${value.trim().replace(/\\*\\*/g, '')}</span>
        </div>`;
      if (impact) {
        card += `<div><span class="fin-impact-badge">Market Impact:</span><span class="fin-impact-text">${impact.trim()}</span></div>`;
      }
      card += `</div>`;
      return card;
    })
    .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
    .replace(/\\*(.*?)\\*/g, '<em>$1</em>')
    .replace(/^### (.*$)/gm, '<h3 class="text-gray-200 mt-3 mb-1 font-bold text-sm">$1</h3>')
    .replace(/^## (.*$)/gm, '<h2 class="text-gray-200 mt-3 mb-1 font-bold text-base">$1</h2>')
    .replace(/^# (.*$)/gm, '<h1 class="text-white mt-4 mb-2 font-bold text-lg">$1</h1>')
    .replace(/^\\- (?!<div)(.*$)/gm, '<li class="ml-4 list-disc text-gray-300">$1</li>')
    .replace(/^\\* (?!<div)(.*$)/gm, '<li class="ml-4 list-disc text-gray-300">$1</li>')
    .replace(/`([^`]+)`/g, '<code class="bg-[#1a1a24] text-[#00ff88] px-1 rounded border border-[#00ff88]/20">$1</code>')
    .replace(/\\n\\n/g, '</p><p class="mt-2 text-gray-300">')
    .replace(/\\n/g, '<br/>');"""

content = content.replace(render_md_old, render_md_new)

# Table styles update inside renderMarkdown
content = content.replace(
    """tableHtml = '<div class="w-full overflow-x-auto mt-2"><table class="w-full text-xs text-left border-collapse">';""",
    """tableHtml = '<div class="w-full overflow-x-auto mt-2"><table class="w-full text-xs text-left border-collapse border border-[#00ff88]/10">';"""
)
content = content.replace(
    """tableHtml += '<tr class="border-b border-border bg-muted/30">' + cells.map(c => `<th class="px-2 py-1 font-mono uppercase tracking-wider text-muted-foreground">${c.trim()}</th>`).join('') + '</tr>';""",
    """tableHtml += '<tr class="border-b border-[#00ff88]/20 bg-[#00ff88]/5">' + cells.map(c => `<th class="px-2 py-1.5 font-mono uppercase tracking-wider text-[#e0e0e0]">${c.trim()}</th>`).join('') + '</tr>';"""
)
content = content.replace(
    """tableHtml += '<tr class="border-b border-border/50 hover:bg-muted/10">' + cells.map(c => `<td class="px-2 py-1 font-data">${c.trim()}</td>`).join('') + '</tr>';""",
    """tableHtml += '<tr class="border-b border-white/5 hover:bg-white/5">' + cells.map(c => `<td class="px-2 py-1.5 text-gray-300">${c.trim()}</td>`).join('') + '</tr>';"""
)


# 4. Thinking steps accordion
thinking_step_old = """function ThinkingStep({ step, message, isActive }) {
  return (
    <div className={`flex items-center gap-2 text-[10px] font-mono transition-all duration-300 ${isActive ? 'text-primary opacity-100' : 'text-muted-foreground opacity-60'}`}>
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${isActive ? 'bg-primary animate-pulse' : 'bg-muted-foreground/50'}`} />
      <span>{message}</span>
    </div>
  );
}"""

thinking_step_new = """function ThinkingAccordion({ steps, isProcessing }) {
  const [expanded, setExpanded] = useState(false);
  
  useEffect(() => {
    if (isProcessing) setExpanded(true);
    else setExpanded(false);
  }, [isProcessing]);
  
  if (!steps || steps.length === 0) return null;

  return (
    <div className="mb-3 border border-[#00ff88]/20 rounded-md bg-[rgba(0,255,136,0.02)] overflow-hidden">
      <button 
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 bg-[rgba(0,255,136,0.05)] hover:bg-[rgba(0,255,136,0.1)] transition-colors"
      >
        <div className="flex items-center gap-2">
          {isProcessing ? (
            <span className="w-1.5 h-1.5 rounded-full bg-[#00ff88] animate-pulse" />
          ) : (
            <span className="text-[#00ff88] font-bold text-xs">✓</span>
          )}
          <span className={`text-[11px] font-mono tracking-wide ${isProcessing ? 'text-[#e0e0e0]' : 'text-[#888]'}`}>
            {isProcessing ? '⚡ Analyzing Markets...' : 'Analysis Complete'}
          </span>
        </div>
        {expanded ? <ChevronDown className="w-3 h-3 text-[#888]" /> : <ChevronRight className="w-3 h-3 text-[#888]" />}
      </button>
      
      {expanded && (
        <div className="px-3 py-2 space-y-2 border-t border-[#00ff88]/10">
          {steps.map((step, i) => (
            <div 
              key={step.id || i} 
              className="flex items-start gap-2 text-[11px] font-mono"
              style={{ animation: `fadeIn 150ms ease-out ${i * 150}ms both` }}
            >
              <span className={`mt-0.5 ${!isProcessing && i === steps.length - 1 ? 'text-[#00ff88]' : 'text-[#888]'}`}>
                [✓]
              </span>
              <span className={!isProcessing || i < steps.length - 1 ? 'text-[#aaa]' : 'text-[#00ff88]'}>
                {step.message}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}"""

content = content.replace(thinking_step_old, thinking_step_new)

# 5. Add generated metadata to final assistant messages
content = content.replace("assistantMsgAdded = true;", "assistantMsgAdded = true;\n                const now = new Date();")
content = content.replace("content: snap, streaming: true };", "content: snap, streaming: true, timestamp: now };")
content = content.replace("content: final, streaming: false };", "content: final, streaming: false, timestamp: now, sources: ['Market APIs'] };")
content = content.replace("content: responseContent }", "content: responseContent, timestamp: new Date(), sources: ['Market APIs'] }")

# 6. UI Updates
container_old = "    <>"
container_new = "    <>\n      <style>{CUSTOM_STYLES}</style>\n"
content = content.replace(container_old, container_new)

# Panel Outer
content = content.replace(
    "className={`fixed z-[999] bg-card flex flex-col overflow-hidden transition-transform duration-300 ease-in-out ${isDesktop",
    "className={`fixed z-[999] flex flex-col overflow-hidden transition-transform duration-300 ease-in-out ${isDesktop"
)
content = content.replace(
    "width: isDesktop ? `${chatWidth}px` : '380px',",
    "width: isDesktop ? `${chatWidth}px` : '380px',\n            backgroundColor: '#0a0a0f',\n            border: '1px solid rgba(0, 255, 136, 0.15)',\n            boxShadow: '0 0 40px rgba(0, 255, 136, 0.05)',\n            borderRadius: isDesktop ? '0' : '12px'"
)

# Header
content = content.replace(
    """<div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/50">""",
    """<div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderBottomColor: 'rgba(0, 255, 136, 0.15)', background: 'linear-gradient(180deg, #0d1117 0%, #0a0a0f 100%)' }}>"""
)

# Replace <Zap /> with custom pulse dot
content = content.replace(
    """<Zap className="w-4 h-4 text-primary" />""",
    """<span className="w-2.5 h-2.5 rounded-full bg-[#00ff88] terminal-pulse" />"""
)

content = content.replace(
    """<span className="font-mono text-sm font-bold text-primary uppercase tracking-wider">""",
    """<span className="font-mono text-sm font-bold text-white uppercase tracking-widest ml-1">"""
)

# Remove the old pulse
content = content.replace(
    """{!showHistory && <span className="w-2 h-2 bg-primary pulse-live" />}""",
    ""
)

# Messages Area Container
content = content.replace(
    """className="flex-1 overflow-y-auto p-3 space-y-3">""",
    """className="flex-1 overflow-y-auto p-3 space-y-3 terminal-scrollbar">"""
)

# Empty state
content = content.replace(
    """<Zap className="w-8 h-8 text-primary/30 mx-auto mb-3" />""",
    """<span className="inline-block w-4 h-4 rounded-full bg-[#00ff88]/30 terminal-pulse mb-3" />"""
)
content = content.replace(
    """hover:border-primary hover:text-primary""",
    """hover:border-[#00ff88]/50 hover:bg-[#00ff88]/5 text-[#aaa] hover:text-[#00ff88]"""
)

# User Message Bubble
content = content.replace(
    """className={`max-w-[85%] px-3 py-2 text-sm ${msg.role === 'user'
                        ? 'bg-primary/10 border border-primary/30 text-foreground'
                        : 'bg-muted border border-border text-foreground'
                        }`}""",
    """className={`px-3 py-2 text-sm ${msg.role === 'user'
                        ? 'bg-[rgba(99,102,241,0.2)] border border-[rgba(99,102,241,0.4)] text-[#e0e0e0] rounded-[12px_12px_2px_12px] text-[13px] ml-auto max-w-[80%]'
                        : 'text-foreground max-w-[95%]'
                        }`}"""
)

# Streaming Pulse inside Assistant Msg
content = content.replace(
    """{msg.streaming && <span className="inline-block w-1.5 h-3 bg-primary ml-1 animate-pulse" />}""",
    """{msg.streaming && <span className="inline-block w-1.5 h-3 bg-[#00ff88] ml-1 animate-pulse" />}"""
)

# Insert Metadata row after assistant message
metadata_row = """                      {msg.role === 'assistant' && !msg.streaming && msg.timestamp && (
                        <div className="flex items-center justify-between mt-2 pt-2 border-t border-white/5">
                          <span className="text-[10px] text-[#444] font-mono">
                            Powered by Gemini • {new Date(msg.timestamp).toLocaleTimeString()}
                          </span>
                          {msg.sources && (
                            <button className="flex items-center gap-1 text-[10px] text-[#00ff88]/60 hover:text-[#00ff88] font-mono transition-colors">
                              <Paperclip className="w-3 h-3" />
                              Data points aggregated
                            </button>
                          )}
                        </div>
                      )}"""
                      
content = content.replace(
    """</div>\n                      ) : (""",
    metadata_row + """\n                        </div>\n                      ) : ("""
)

# Tool execution accordion mapping
content = content.replace(
    """{/* Thinking Steps */}
                {thinkingSteps.length > 0 && (
                  <div className="flex justify-start">
                    <div className="bg-muted/50 border border-border/50 px-3 py-2 space-y-1.5 min-w-[200px]">
                      {thinkingSteps.map((step, i) => (
                        <ThinkingStep key={step.id || i} step={step.step} message={step.message} isActive={i === thinkingSteps.length - 1} />
                      ))}
                    </div>
                  </div>
                )}""",
    """{/* Thinking Steps (Reasoning Accordion) */}
                <ThinkingAccordion steps={thinkingSteps} isProcessing={thinkingSteps.length > 0 && messages[messages.length-1]?.role === 'user'} />"""
)

# Input Bar Loading State Update (Equalizer)
loading_indicator_old = """disabled={loading || !input.trim()}
                    className="rounded-none bg-primary text-black hover:bg-primary/80 px-3 h-[36px]"
                  >
                    <Send className="w-3 h-3" />"""
loading_indicator_new = """disabled={loading || !input.trim()}
                    className="rounded-md bg-[#00ff88] text-black hover:bg-[#00ff88] hover:scale-105 transition-transform px-3 h-[40px] ml-2"
                  >
                    <Send className="w-4 h-4" />"""
content = content.replace(loading_indicator_old, loading_indicator_new)

# Add the loading "Querying live market data..."
# Wait, actually let's just make the loading state appear where the thoughts appear. The user requested:
# "Replace spinner with 3 animated green equalizer bars... Show 'Querying live market data...'"
# If we show this globally or in the input area? It says "7. LOADING STATE".
# Let's add it in the messages area when loading is true and thinkingSteps is empty (which happens while waiting for the first chunk).
loading_html = """{loading && thinkingSteps.length === 0 && (
                  <div className="flex items-center gap-3 px-2 py-3">
                    <div className="flex items-end gap-[3px] h-4">
                      <div className="eq-bar h-2" />
                      <div className="eq-bar h-4" />
                      <div className="eq-bar h-2" />
                    </div>
                    <span className="text-[11px] font-mono text-[#555]">Querying live market data...</span>
                  </div>
                )}"""
content = content.replace("{/* Follow-up Questions */}", loading_html + "\n                {/* Follow-up Questions */}")

# Input container tweaks
content = content.replace(
    """<div className="p-3 border-t border-border">""",
    """<div className="p-3" style={{ borderTop: '1px solid rgba(0, 255, 136, 0.15)', background: 'linear-gradient(0deg, #0d1117 0%, #0a0a0f 100%)' }}>"""
)
content = content.replace(
    """<textarea
                    ref={textareaRef}""",
    """<div className="relative flex-1 flex items-end">
                  <textarea
                    ref={textareaRef}"""
)
content = content.replace(
    """disabled={loading || (!aiUsage.unlimited && aiUsage.remaining <= 0)}
                  />""",
    """disabled={loading || (!aiUsage.unlimited && aiUsage.remaining <= 0)}
                  />
                  <span className="absolute right-3 top-[50%] -translate-y-[50%] text-[#555] pointer-events-none text-xs hidden sm:block">⏎</span>
                  </div>"""
)
content = content.replace(
    """className="flex-1 rounded-md bg-background border border-border font-mono text-xs focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none resize-none overflow-y-auto px-3 py-2 min-h-[36px]\"""",
    """className="flex-1 w-full bg-[rgba(255,255,255,0.04)] text-white border border-[rgba(255,255,255,0.1)] focus:border-[rgba(0,255,136,0.5)] focus:ring-0 focus:shadow-[0_0_0_2px_rgba(0,255,136,0.1)] rounded-md font-mono text-xs px-3 py-2.5 min-h-[40px] resize-none terminal-scrollbar\""""
)

with open(FILE_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated AIChatbot.js successfully.")
