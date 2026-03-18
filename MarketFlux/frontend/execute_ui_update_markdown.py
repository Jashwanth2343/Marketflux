import os

FILE_PATH = "src/components/AIChatbot.js"

with open(FILE_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update renderMarkdown to meet the new style rules
render_md_old = """  let html = text
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
    .replace(/^### (.*$)/gm, '<h3 class="mt-3 mb-1 font-bold text-sm opacity-90">$1</h3>')
    .replace(/^## (.*$)/gm, '<h2 class="mt-3 mb-1 font-bold text-base opacity-90">$1</h2>')
    .replace(/^# (.*$)/gm, '<h1 class="mt-4 mb-2 font-bold text-lg">$1</h1>')
    .replace(/^\\- (?!<div)(.*$)/gm, '<li class="ml-4 list-disc opacity-90">$1</li>')
    .replace(/^\\* (?!<div)(.*$)/gm, '<li class="ml-4 list-disc opacity-90">$1</li>')"""

render_md_new = """  let html = text
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
    .replace(/^### (.*$)/gm, '<h3 style="color: #e8e8e8; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 16px; margin-bottom: 8px;">$1</h3>')
    .replace(/\\*\\*(.*?)\\*\\*/g, '<strong style="color: #ffffff; font-weight: 700;">$1</strong>')
    .replace(/^(?:-|\\*)\\s+(?!<div)(.*$)/gm, '<div style="color: #aaa; margin-left: 12px; text-indent: -12px;">&bull; $1</div>')
    .replace(/\\*(.*?)\\*/g, '<em>$1</em>')
    .replace(/^## (.*$)/gm, '<h2 class="mt-3 mb-1 font-bold text-base opacity-90">$1</h2>')
    .replace(/^# (.*$)/gm, '<h1 class="mt-4 mb-2 font-bold text-lg">$1</h1>')"""

content = content.replace(render_md_old, render_md_new)


# 2. Extract Collapsible Markdown Component
collapsible_component = """
function CollapsibleMarkdown({ content, isError, streaming }) {
  const [expanded, setExpanded] = useState(false);
  
  // Only truncate if not streaming, otherwise the user sees a jarring cut during generation
  const words = content.split(/\\s+/);
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
          className="mt-3 text-[#00ff88] text-[11px] hover:underline cursor-pointer font-sans transition-colors block"
        >
          {expanded ? 'Show less ▴' : 'Show full analysis ▾'}
        </button>
      )}
    </div>
  );
}
"""

if "function CollapsibleMarkdown" not in content:
    content = content.replace("function ThinkingAccordion", collapsible_component + "\nfunction ThinkingAccordion")


# 3. Use CollapsibleMarkdown in Assistant Message
old_markdown_render = """<div className="relative">
                            <div
                              className={`markdown-content text-xs leading-relaxed ${msg.isError ? 'text-destructive' : ''}`}
                              dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) || '' }}
                            />
                            {msg.streaming && <span className="inline-block w-1.5 h-3 bg-primary ml-1 animate-pulse" />}
                          </div>"""

new_markdown_render = """<CollapsibleMarkdown content={msg.content} isError={msg.isError} streaming={msg.streaming} />"""

content = content.replace(old_markdown_render, new_markdown_render)

# 4. Change follow-up question chips to sans-serif
content = content.replace(
    """className="block w-full text-left text-[11px] px-3 py-2 border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors font-mono rounded\"""",
    """className="block w-full text-left text-[11px] px-3 py-2 border border-border text-muted-foreground hover:border-primary hover:text-primary transition-colors font-sans rounded\""""
)

# 5. Fix table rendering inside renderMarkdown that still had `html = result.replace...`
old_table_replaces = """    html = result
      .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code class="bg-muted text-primary px-1 rounded border border-primary/20">$1</code>')
      .replace(/\\n/g, '<br/>');"""
      
new_table_replaces = """    html = result
      .replace(/\\*\\*(.*?)\\*\\*/g, '<strong style="color: #ffffff; font-weight: 700;">$1</strong>')
      .replace(/`([^`]+)`/g, '<code class="bg-muted text-primary px-1 rounded border border-primary/20">$1</code>')
      .replace(/\\n/g, '<br/>');"""

content = content.replace(old_table_replaces, new_table_replaces)


with open(FILE_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated AIChatbot.js markdown logic successfully.")
