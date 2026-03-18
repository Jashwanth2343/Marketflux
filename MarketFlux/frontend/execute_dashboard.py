import os

FILE_PATH = "src/pages/Dashboard.js"

with open(FILE_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# Remove recharts from Dashboard imports
content = content.replace(
    "import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';",
    "" # We don't need it. But let's just replace it safely.
)

# Insert the Speedometer Component before Dashboard component
speedometer_code = """
function SpeedometerGauge({ score, mood }) {
    // Determine label and color based on score
    let label = 'NEUTRAL';
    let color = '#eab308'; // yellow
    if (score < 25) { label = 'EXTREME FEAR'; color = '#ef4444'; }
    else if (score < 45) { label = 'FEAR'; color = '#f97316'; }
    else if (score > 75) { label = 'EXTREME GREED'; color = '#22c55e'; }
    else if (score > 55) { label = 'GREED'; color = '#84cc16'; }

    // Needle rotation (-90 is left/0, +90 is right/100)
    const angle = -90 + (score / 100) * 180;

    return (
        <div className="flex flex-col items-center justify-center w-full relative pt-2">
            <svg viewBox="0 0 200 120" className="w-full max-w-[280px] drop-shadow-md overflow-visible relative">
                <defs>
                    <linearGradient id="speedGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#ef4444" />
                        <stop offset="25%" stopColor="#f97316" />
                        <stop offset="50%" stopColor="#eab308" />
                        <stop offset="75%" stopColor="#84cc16" />
                        <stop offset="100%" stopColor="#22c55e" />
                    </linearGradient>
                </defs>
                
                {/* Track background */}
                <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="rgba(255,255,255,0.06)" className="dark:stroke-[rgba(255,255,255,0.06)] stroke-slate-200" strokeWidth="12" strokeLinecap="round" />
                
                {/* Colored Gradient Arc */}
                <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="url(#speedGradient)" strokeWidth="12" strokeLinecap="round" />

                {/* Needle */}
                <g transform={`rotate(${angle}, 100, 100)`} className="transition-transform duration-1000 ease-out">
                    <line x1="100" y1="100" x2="100" y2="25" stroke="var(--color-accent, #00ff88)" strokeWidth="3" strokeLinecap="round" />
                    <circle cx="100" cy="100" r="4" fill="var(--color-accent, #00ff88)" />
                </g>

                {/* Zone Labels */}
                <text x="20" y="115" fontSize="9" fill="#ef4444" textAnchor="middle" className="font-mono font-bold tracking-wider">FEAR</text>
                <text x="100" y="115" fontSize="9" fill="#eab308" textAnchor="middle" className="font-mono font-bold tracking-wider">NEUTRAL</text>
                <text x="180" y="115" fontSize="9" fill="#22c55e" textAnchor="middle" className="font-mono font-bold tracking-wider">GREED</text>

                {/* Score Text inside arc */}
                <text x="100" y="80" fontSize="36" fontWeight="800" fill={color} textAnchor="middle" className="font-sans drop-shadow-sm">{score}</text>
                <text x="100" y="95" fontSize="11" fill={color} textAnchor="middle" letterSpacing="0.1em" className="font-mono font-bold">{label}</text>
            </svg>
            
            {/* The Badge logic that existed before is moved up to CardHeader in original container, but we keep this clean here. */}
        </div>
    );
}
"""

if "function SpeedometerGauge" not in content:
    content = content.replace("export default function Dashboard() {", speedometer_code + "\nexport default function Dashboard() {")

# Replace pie chart with speedometer gauge
pie_chart_block = """<div className="flex-1 min-h-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={moodData} dataKey="value" cx="50%" cy="50%" innerRadius="55%" outerRadius="80%" strokeWidth={0}>
                    {moodData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: '#0A0A0A', border: '1px solid #1E293B', borderRadius: '8px', fontFamily: 'Inter' }}
                    itemStyle={{ color: '#EDEDED', fontSize: '12px', fontWeight: 'bold' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-3 mt-4 px-2">
              {moodData.map(m => (
                <div key={m.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: m.color }} />
                    <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">{m.name}</span>
                  </div>
                  <span className="font-data text-sm font-bold text-foreground">{m.value}</span>
                </div>
              ))}
            </div>"""

speedometer_metrics_block = """<div className="flex-1 flex flex-col items-center justify-center min-h-0 mt-4 mb-2">
              <SpeedometerGauge score={mood.fng_index || 50} mood={mood} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mt-4 px-1 pb-1">
              <div className="dark:bg-[rgba(255,255,255,0.03)] bg-slate-50 border dark:border-[rgba(255,255,255,0.08)] border-slate-200 rounded-[8px] p-2 flex flex-col items-center justify-center text-center">
                <span className="text-[9px] text-[#666] uppercase tracking-[0.08em] font-mono mb-1">MARKET MOMENTUM</span>
                <span className={`text-[13px] font-bold font-sans ${mood.dominant === 'bullish' ? 'text-[#22c55e]' : 'text-[#ef4444]'}`}>
                  {mood.dominant === 'bullish' ? '↑ Bullish' : '↓ Bearish'}
                </span>
              </div>
              <div className="dark:bg-[rgba(255,255,255,0.03)] bg-slate-50 border dark:border-[rgba(255,255,255,0.08)] border-slate-200 rounded-[8px] p-2 flex flex-col items-center justify-center text-center">
                <span className="text-[9px] text-[#666] uppercase tracking-[0.08em] font-mono mb-1">VOLATILITY(VIX)</span>
                <span className="text-[13px] font-bold font-sans text-foreground">
                  29.49 (+24%)
                </span>
              </div>
              <div className="dark:bg-[rgba(255,255,255,0.03)] bg-slate-50 border dark:border-[rgba(255,255,255,0.08)] border-slate-200 rounded-[8px] p-2 flex flex-col items-center justify-center text-center">
                <span className="text-[9px] text-[#666] uppercase tracking-[0.08em] font-mono mb-1">MARKET BREADTH</span>
                <span className={`text-[13px] font-bold font-sans text-foreground`}>
                  Bearish: {mood.bearish || 88}%
                </span>
              </div>
            </div>"""

content = content.replace(pie_chart_block, speedometer_metrics_block)

with open(FILE_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Updated {FILE_PATH} successfully.")
