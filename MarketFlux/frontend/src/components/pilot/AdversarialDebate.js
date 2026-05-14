import { useMemo } from 'react';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';

const AGENT_PALETTE = {
  bull: {
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    text: 'text-emerald-400',
    avatarBg: 'bg-emerald-500/20',
  },
  bear: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    text: 'text-red-400',
    avatarBg: 'bg-red-500/20',
  },
  value: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    text: 'text-amber-400',
    avatarBg: 'bg-amber-500/20',
  },
  momentum: {
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30',
    text: 'text-cyan-400',
    avatarBg: 'bg-cyan-500/20',
  },
  risk: {
    bg: 'bg-violet-500/10',
    border: 'border-violet-500/30',
    text: 'text-violet-400',
    avatarBg: 'bg-violet-500/20',
  },
};

const DEFAULT_PALETTE = {
  bg: 'bg-muted/40',
  border: 'border-border',
  text: 'text-muted-foreground',
  avatarBg: 'bg-muted',
};

function paletteFor(agentKey) {
  if (!agentKey) return DEFAULT_PALETTE;
  const key = String(agentKey).toLowerCase();
  return AGENT_PALETTE[key] || DEFAULT_PALETTE;
}

export function AdversarialDebate({ transcript, verdict, compact = false }) {
  const bubbles = useMemo(() => (Array.isArray(transcript) ? transcript : []), [transcript]);

  if (!bubbles.length) {
    return (
      <div className="text-xs font-mono uppercase tracking-wider text-muted-foreground p-3">
        No debate transcript available yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {bubbles.map((bubble, idx) => {
        const palette = paletteFor(bubble?.agent);
        const name = bubble?.name || bubble?.agent || `Agent ${idx + 1}`;
        const initial = (name || '?').trim().charAt(0).toUpperCase();
        const content = bubble?.content || '';

        return (
          <motion.div
            key={`${bubble?.agent || 'agent'}-${idx}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.08, duration: 0.25 }}
            className={`rounded-lg border ${palette.border} ${palette.bg} p-3 flex gap-3`}
          >
            <div
              className={`w-8 h-8 shrink-0 rounded-full flex items-center justify-center font-mono text-sm font-bold ${palette.avatarBg} ${palette.text}`}
            >
              {initial}
            </div>
            <div className="flex-1 min-w-0">
              <div className={`text-[10px] font-mono uppercase tracking-wider ${palette.text} mb-1`}>
                {name}
              </div>
              <div
                className={`text-sm leading-relaxed text-foreground/90 prose prose-invert prose-sm max-w-none ${
                  compact ? 'line-clamp-6' : ''
                }`}
              >
                <ReactMarkdown>{content}</ReactMarkdown>
              </div>
            </div>
          </motion.div>
        );
      })}

      {verdict ? (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: bubbles.length * 0.08, duration: 0.25 }}
          className="rounded-lg border border-primary/30 bg-primary/10 p-3"
        >
          <div className="text-[10px] font-mono uppercase tracking-wider text-primary mb-1">Verdict</div>
          <div className="text-sm text-foreground/90 prose prose-invert prose-sm max-w-none">
            <ReactMarkdown>{verdict}</ReactMarkdown>
          </div>
        </motion.div>
      ) : null}
    </div>
  );
}
