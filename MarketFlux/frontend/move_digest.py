import re

with open("/Users/jashwanthkanderi/Downloads/Financegptwebdashboard-main/MarketFlux/frontend/src/pages/StockDetail.js", "r") as f:
    content = f.read()

# Pattern for the digest section
digest_pattern = r"(      {/\* Flux AI Digest \*/}\n      <Card className=\"rounded-none border-primary/20 bg-card/50\" data-testid=\"ai-digest-section\">.*?      </Card>\n\n)"
digest_match = re.search(digest_pattern, content, flags=re.DOTALL)

if not digest_match:
    print("Digest not found.")
    exit(1)

digest_text = digest_match.group(1)
content = content.replace(digest_text, "")

# Modern 2026 styling
new_digest = """      {/* Flux AI Digest - Moved to Top */}
      <Card className="rounded-xl border border-primary/40 bg-background/60 backdrop-blur-xl shadow-[0_0_30px_rgba(0,255,65,0.15)] mb-6 relative overflow-hidden" data-testid="ai-digest-section">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent opacity-50 pointer-events-none" />
        <CardHeader className="pb-2 pt-4 px-5 flex flex-row items-center justify-between relative z-10 border-b border-border/30">
          <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" /> Flux AI Digest
            <span className="w-2 h-2 rounded-full bg-primary pulse-live" />
          </CardTitle>
          <div className="flex items-center gap-3">
            {digestAge != null && (
              <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">
                {digestAge < 1 ? 'Just refreshed' : `${digestAge}m ago`}
              </span>
            )}
            <Button
              data-testid="refresh-digest"
              variant="default"
              size="sm"
              onClick={() => fetchDigest(true)}
              disabled={digestLoading}
              className="rounded-md text-xs font-mono bg-primary/10 text-primary hover:bg-primary/20 hover:text-primary shadow-none border border-primary/20 p-2 h-auto transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${digestLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="px-5 pb-5 relative z-10 pt-4">
          {digestLoading && !digest ? (
            <div className="py-8 flex flex-col items-center gap-3">
              <Loader2 className="w-5 h-5 animate-spin text-primary" />
              <span className="font-mono text-xs text-muted-foreground uppercase tracking-widest">Generating Analyst Digest<span className="cursor-blink">_</span></span>
            </div>
          ) : digest?.digest ? (
            <div className="bg-muted/10 rounded-lg p-1">
              <div className="markdown-content text-[13.5px] leading-relaxed text-foreground/90 font-medium" dangerouslySetInnerHTML={{ __html: renderMarkdown(digest.digest) }} />
            </div>
          ) : (
            <p className="text-xs font-mono text-muted-foreground py-6 text-center uppercase tracking-widest">Digest unavailable. Click refresh to try again.</p>
          )}
        </CardContent>
      </Card>

"""

# Insert right after the chart card
chart_end = "      </Card>\n\n      {/* Stats + Fundamentals Grid */}"
content = content.replace(chart_end, "      </Card>\n\n" + new_digest + "      {/* Stats + Fundamentals Grid */}")

with open("/Users/jashwanthkanderi/Downloads/Financegptwebdashboard-main/MarketFlux/frontend/src/pages/StockDetail.js", "w") as f:
    f.write(content)

print("Done")
