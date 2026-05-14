import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, Play, Pause, Copy, Zap } from 'lucide-react';

import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { KillSwitchButton } from '@/components/pilot/KillSwitchButton';

const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const GLYPHS = {
  circle: (color) => (
    <span
      className="inline-block w-4 h-4 rounded-full"
      style={{ backgroundColor: color, boxShadow: `0 0 8px ${color}66` }}
    />
  ),
  triangle: (color) => (
    <span
      className="inline-block"
      style={{
        width: 0,
        height: 0,
        borderLeft: '8px solid transparent',
        borderRight: '8px solid transparent',
        borderBottom: `14px solid ${color}`,
        filter: `drop-shadow(0 0 4px ${color}66)`,
      }}
    />
  ),
  square: (color) => (
    <span
      className="inline-block w-4 h-4 rounded-sm"
      style={{ backgroundColor: color, boxShadow: `0 0 8px ${color}66` }}
    />
  ),
  hexagon: (color) => (
    <span
      className="inline-block w-4 h-4"
      style={{
        backgroundColor: color,
        clipPath: 'polygon(25% 5%, 75% 5%, 100% 50%, 75% 95%, 25% 95%, 0% 50%)',
        boxShadow: `0 0 8px ${color}66`,
      }}
    />
  ),
};

function Glyph({ shape, color }) {
  const render = GLYPHS[shape] || GLYPHS.circle;
  return render(color || '#22c55e');
}

export function PersonalityCard({
  personality,
  selected = false,
  onSelect,
  onUpdated,
  onProposed,
}) {
  const [proposing, setProposing] = useState(false);
  const [pausing, setPausing] = useState(false);
  const [cloning, setCloning] = useState(false);

  if (!personality) return null;

  const accent = personality.accent_color || '#22c55e';
  const paused = !!personality.paused;
  const isSeed = !!personality.is_seed;

  const handleSelect = () => {
    onSelect?.(personality);
  };

  const togglePause = async (next) => {
    setPausing(true);
    try {
      const endpoint = next ? 'pause' : 'resume';
      // next === true means user wants paused (off the switch). Switch shows ENABLED state when running.
      // We use the new state: "checked" on the Switch represents "running" (not paused).
      // So when the user toggles to running (checked=true), we hit resume.
      const url = `${API}/api/pilot/personalities/${personality.id}/${endpoint}`;
      const res = await axios.post(url, {}, { withCredentials: true });
      const updated = res?.data?.item;
      if (updated) onUpdated?.(updated);
      toast.success(`${personality.name} ${next ? 'paused' : 'resumed'}.`);
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        'Unknown error';
      toast.error(`Could not toggle ${personality.name}. Backend says: ${String(detail)}`);
    } finally {
      setPausing(false);
    }
  };

  const handleSwitchChange = (checked) => {
    // checked = true => running, false => paused
    togglePause(!checked);
  };

  const propose = async (e) => {
    e?.stopPropagation?.();
    if (paused) {
      toast.info(`${personality.name} is paused. Resume it first.`);
      return;
    }
    setProposing(true);
    try {
      const res = await axios.post(
        `${API}/api/pilot/personalities/${personality.id}/propose`,
        { max_candidates: 5, dry_run: false },
        { withCredentials: true }
      );
      const data = res?.data || {};
      if (data.ok === false) {
        toast.info(
          `${personality.name}: ${data.reason || data.message || 'No proposals generated.'}`
        );
      } else {
        const count = Array.isArray(data.proposals) ? data.proposals.length : 0;
        toast.success(`${personality.name} found ${count} proposal${count === 1 ? '' : 's'}.`);
      }
      onProposed?.(data);
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        'Unknown error';
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg || d.message || JSON.stringify(d)).join('; ')
        : String(detail);
      toast.error(`Could not propose trades. Backend says: ${msg}`);
    } finally {
      setProposing(false);
    }
  };

  const clone = async (e) => {
    e?.stopPropagation?.();
    setCloning(true);
    try {
      const res = await axios.post(
        `${API}/api/pilot/personalities/${personality.id}/clone`,
        {},
        { withCredentials: true }
      );
      const item = res?.data?.item;
      toast.success(`Cloned ${personality.name}. Edit your copy any time.`);
      onUpdated?.(item, { isClone: true });
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        'Unknown error';
      toast.error(`Could not clone ${personality.name}. Backend says: ${String(detail)}`);
    } finally {
      setCloning(false);
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleSelect}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleSelect();
        }
      }}
      className={`relative bg-card border rounded-lg p-4 cursor-pointer transition-all min-h-[160px] flex flex-col gap-2 hover:bg-card/80 ${
        selected ? 'ring-2 shadow-lg' : 'border-border'
      }`}
      style={{
        borderLeft: `4px solid ${accent}`,
        boxShadow: selected ? `0 0 0 1px ${accent}, 0 0 14px ${accent}33` : undefined,
        // Pass accent as the ring color when selected
        ['--tw-ring-color']: accent,
      }}
    >
      {/* Top row: glyph + name + pause switch */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Glyph shape={personality.avatar_glyph} color={accent} />
          <div className="min-w-0">
            <div className="text-sm font-semibold text-foreground truncate" style={{ color: accent }}>
              {personality.name}
            </div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
              {personality.cadence || 'daily'} · v{personality.version || 1}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
          <Switch
            checked={!paused}
            onCheckedChange={handleSwitchChange}
            disabled={pausing}
            aria-label={paused ? 'Resume personality' : 'Pause personality'}
          />
        </div>
      </div>

      {/* Mandate */}
      <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
        {personality.mandate || 'No mandate set.'}
      </p>

      {/* Status / chips */}
      <div className="flex flex-wrap gap-1.5">
        {paused ? (
          <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-yellow-500/10 text-yellow-500 border border-yellow-500/30">
            Paused
          </span>
        ) : (
          <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-green-500/10 text-green-500 border border-green-500/30">
            Live
          </span>
        )}
        {isSeed ? (
          <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border">
            Seed
          </span>
        ) : null}
        {personality.universe?.length ? (
          <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border">
            {personality.universe.length} tickers
          </span>
        ) : null}
      </div>

      {/* Actions */}
      <div className="mt-auto flex flex-wrap items-center gap-2 pt-2" onClick={(e) => e.stopPropagation()}>
        <Button
          type="button"
          size="sm"
          onClick={propose}
          disabled={proposing || paused}
          className="gap-1 font-mono text-xs uppercase tracking-wider"
        >
          {proposing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
          {proposing ? 'Thinking' : 'Propose'}
        </Button>

        {isSeed ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={clone}
            disabled={cloning}
            className="gap-1 font-mono text-xs uppercase tracking-wider"
          >
            {cloning ? <Loader2 className="w-3 h-3 animate-spin" /> : <Copy className="w-3 h-3" />}
            Clone
          </Button>
        ) : null}

        <KillSwitchButton
          personalityId={personality.id}
          personalityName={personality.name}
          size="sm"
          variant="destructive"
          onKilled={(data) => {
            // Mark personality paused locally
            onUpdated?.({ ...personality, paused: true }, { killed: true, killData: data });
          }}
        />

        {paused ? (
          <span className="ml-auto text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center gap-1">
            <Pause className="w-3 h-3" /> off
          </span>
        ) : (
          <span className="ml-auto text-[10px] font-mono uppercase tracking-wider text-green-500 flex items-center gap-1">
            <Play className="w-3 h-3" /> on
          </span>
        )}
      </div>
    </div>
  );
}
