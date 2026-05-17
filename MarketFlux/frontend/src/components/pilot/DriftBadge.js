import { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import api from '@/lib/api';

/**
 * Lightweight chip that appears on a PersonalityCard when one or more open
 * positions have drifted past the personality's entry signal. Polls on a
 * slow cadence; silently disappears when there is nothing to surface.
 *
 * Props:
 *   - personalityId: string, required
 *   - className: optional
 *   - pollMs: poll cadence (default 90s); set to 0 to fetch once only
 *   - onClick: optional click handler (we surface flags via parent for now)
 */
export function DriftBadge({ personalityId, className = '', pollMs = 90_000, onClick }) {
  const [flags, setFlags] = useState([]);

  useEffect(() => {
    if (!personalityId) return undefined;
    let cancelled = false;

    const fetchOnce = async () => {
      try {
        const res = await api.get(
          `/pilot/personalities/${personalityId}/drift`
        );
        if (!cancelled) setFlags(res?.data?.items || []);
      } catch {
        if (!cancelled) setFlags([]);
      }
    };

    fetchOnce();
    if (!pollMs) return () => { cancelled = true; };
    const id = setInterval(fetchOnce, pollMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [personalityId, pollMs]);

  if (!flags.length) return null;

  const high = flags.filter((f) => f.severity === 'high').length;
  const colorCls = high
    ? 'bg-red-500/10 text-red-500 border-red-500/40'
    : 'bg-amber-500/10 text-amber-400 border-amber-500/40';

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick?.(flags);
      }}
      className={`inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border ${colorCls} ${className}`}
      title={flags
        .map(
          (f) =>
            `${f.ticker}: ${f.entry_score.toFixed(0)} → ${f.current_score.toFixed(0)} (${
              f.delta > 0 ? '+' : ''
            }${f.delta.toFixed(0)})`
        )
        .join('\n')}
    >
      <AlertTriangle className="w-3 h-3" />
      {flags.length} drift{flags.length === 1 ? '' : 's'}
      {high ? ` · ${high} high` : ''}
    </button>
  );
}

export default DriftBadge;
