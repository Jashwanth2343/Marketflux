import { useEffect, useState, useRef } from 'react';
import { toast } from 'sonner';
import { Check, X, Eye, Loader2, CheckCircle2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import api from '@/lib/api';
const STATUS_POLL_INTERVAL_MS = 2000;
const MAX_STATUS_POLL_ATTEMPTS = 15;
const STATUS_POLLING_STATES = new Set(['pending', 'approved']);

function formatCurrency(value) {
  if (value === null || value === undefined || value === '') return '--';
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

function useCountdown(targetIso) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!targetIso) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [targetIso]);

  if (!targetIso) return null;
  const target = new Date(targetIso).getTime();
  if (Number.isNaN(target)) return null;
  const diff = Math.max(0, target - now);
  const totalSec = Math.floor(diff / 1000);
  if (totalSec <= 0) return 'expired';
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function ProposalCard({ proposal, onDetails, onChanged, onDismiss }) {
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [local, setLocal] = useState(proposal);
  const [showExecutedToast, setShowExecutedToast] = useState(false);
  const dismissTimerRef = useRef(null);
  const statusPollTimerRef = useRef(null);
  const statusPollRunRef = useRef(0);

  useEffect(() => {
    setLocal(proposal);
  }, [proposal]);

  useEffect(() => {
    return () => {
      if (dismissTimerRef.current) {
        clearTimeout(dismissTimerRef.current);
      }
      if (statusPollTimerRef.current) {
        clearTimeout(statusPollTimerRef.current);
      }
    };
  }, []);

  const countdown = useCountdown(local?.expires_at);

  if (!local) return null;

  const composite = local?.signal_snapshot?.composite_score;
  const compositeColor =
    typeof composite === 'number'
      ? composite >= 60
        ? 'text-green-500 border-green-500/30 bg-green-500/10'
        : composite <= 40
        ? 'text-red-500 border-red-500/30 bg-red-500/10'
        : 'text-amber-400 border-amber-500/30 bg-amber-500/10'
      : 'text-muted-foreground border-border bg-muted/40';

  const allowed = local?.policy_verdict?.allowed;

  const triggerExecutedDismiss = () => {
    setShowExecutedToast(true);
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
    dismissTimerRef.current = setTimeout(() => {
      onDismiss?.(local.id);
    }, 10_000);
  };

  const stopStatusPolling = () => {
    if (statusPollTimerRef.current) {
      clearTimeout(statusPollTimerRef.current);
      statusPollTimerRef.current = null;
    }
  };

  const refreshProposal = async () => {
    try {
      const res = await api.get(`/pilot/proposals/${local.id}`);
      const item = res?.data?.item;
      if (item) {
        setLocal(item);
        onChanged?.(item);
        if (item.status === 'executed') {
          toast.success(
            `Executed ${item.ticker} at ${formatCurrency(item.fill_price || item.quote_price)}`
          );
          triggerExecutedDismiss();
        } else if (item.status === 'failed') {
          toast.error(
            `Execution failed for ${item.ticker}. ${item.status_reason || ''}`.trim()
          );
        }
        return item;
      }
    } catch {
      // Silent — we already toasted on approve. Avoid noisy refresh errors.
    }
    return null;
  };

  const approve = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await api.post(
        `/pilot/proposals/${local.id}/approve`,
        {}
      );
      const item = res?.data?.item;
      if (item) {
        setLocal(item);
        onChanged?.(item);
      }
      toast.success(`Approved ${local.ticker}. Routing to paper account…`);
      setConfirmOpen(false);
      // Poll for execution status for up to ~30s to avoid missing slow async fills.
      stopStatusPolling();
      statusPollRunRef.current += 1;
      const runId = statusPollRunRef.current;
      let attempts = 0;
      const poll = async () => {
        if (runId !== statusPollRunRef.current) return;
        attempts += 1;
        const item = await refreshProposal();
        if (runId !== statusPollRunRef.current) return;
        const status = item?.status;
        if (status !== undefined && status !== null && !STATUS_POLLING_STATES.has(status)) {
          stopStatusPolling();
          return;
        }
        if (attempts < MAX_STATUS_POLL_ATTEMPTS) {
          statusPollTimerRef.current = setTimeout(poll, STATUS_POLL_INTERVAL_MS);
        } else {
          stopStatusPolling();
        }
      };
      statusPollTimerRef.current = setTimeout(poll, STATUS_POLL_INTERVAL_MS);
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        'Unknown error';
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg || d.message || JSON.stringify(d)).join('; ')
        : String(detail);
      toast.error(`Could not approve. Backend says: ${msg}`);
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    setBusy(true);
    try {
      const res = await api.post(
        `/pilot/proposals/${local.id}/reject`,
        {}
      );
      const item = res?.data?.item;
      if (item) {
        setLocal(item);
        onChanged?.(item);
      }
      toast.success(`Rejected ${local.ticker}.`);
      setRejectOpen(false);
      // Remove from queue shortly after
      if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current);
      dismissTimerRef.current = setTimeout(() => {
        onDismiss?.(local.id);
      }, 1500);
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        'Unknown error';
      toast.error(`Could not reject. Backend says: ${String(detail)}`);
    } finally {
      setBusy(false);
    }
  };

  // Executed compact state
  if (local.status === 'executed' || showExecutedToast) {
    return (
      <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3 flex items-center gap-2 text-sm">
        <CheckCircle2 className="w-4 h-4 text-green-500" />
        <span className="text-foreground">
          Executed {local.ticker} at {formatCurrency(local.fill_price || local.quote_price)}
        </span>
      </div>
    );
  }

  return (
    <>
      <div className="bg-card border border-border rounded-lg p-4 space-y-3">
        {/* Header summary */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="font-mono text-sm uppercase tracking-wider">
              <span
                className={
                  local.side === 'buy' ? 'text-green-500' : 'text-red-500'
                }
              >
                {(local.side || '').toUpperCase()}
              </span>{' '}
              <span className="font-bold text-foreground">{local.qty}</span>{' '}
              <span className="text-foreground">{local.ticker}</span>{' '}
              <span className="text-muted-foreground">@ {formatCurrency(local.quote_price)}</span>
            </div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mt-0.5">
              {local.personality_name || 'Pilot'} ·{' '}
              {local.conviction != null ? `conviction ${local.conviction}/10` : 'conviction --'}
            </div>
          </div>
        </div>

        {/* Thesis */}
        <p className="text-xs text-foreground/80 leading-relaxed line-clamp-2">
          {local.thesis || 'No thesis provided.'}
        </p>

        {/* Pills */}
        <div className="flex flex-wrap gap-1.5">
          <span
            className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border ${compositeColor}`}
          >
            Signal {typeof composite === 'number' ? composite.toFixed(0) : '--'}
          </span>
          <span
            className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border ${
              allowed
                ? 'text-green-500 border-green-500/30 bg-green-500/10'
                : 'text-red-500 border-red-500/30 bg-red-500/10'
            }`}
          >
            {allowed ? 'Policy OK' : 'Policy block'}
          </span>
          <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border">
            Notional {formatCurrency(local.proposed_notional)}
          </span>
          {local.stop_loss_price ? (
            <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/30">
              SL {formatCurrency(local.stop_loss_price)}
            </span>
          ) : null}
          {local.take_profit_price ? (
            <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-green-500/10 text-green-500 border border-green-500/30">
              TP {formatCurrency(local.take_profit_price)}
            </span>
          ) : null}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 pt-1">
          <Button
            size="sm"
            onClick={() => setConfirmOpen(true)}
            disabled={busy || local.status !== 'pending'}
            className="gap-1 font-mono text-xs uppercase tracking-wider"
          >
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
            Approve
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setRejectOpen(true)}
            disabled={busy || local.status !== 'pending'}
            className="gap-1 font-mono text-xs uppercase tracking-wider"
          >
            <X className="w-3 h-3" /> Reject
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onDetails?.(local)}
            className="gap-1 font-mono text-xs uppercase tracking-wider ml-auto"
          >
            <Eye className="w-3 h-3" /> Details
          </Button>
        </div>

        {/* Countdown */}
        {countdown ? (
          <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            Expires in {countdown}
          </div>
        ) : null}
      </div>

      {/* Approve confirm */}
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Approve paper trade?</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="font-mono">
                {(local.side || '').toUpperCase()} {local.qty} {local.ticker} @{' '}
                {formatCurrency(local.quote_price)}
              </span>
              <br />
              Notional <span className="font-mono">{formatCurrency(local.proposed_notional)}</span>
              {local.stop_loss_price ? (
                <>
                  {' '}· stop <span className="font-mono">{formatCurrency(local.stop_loss_price)}</span>
                </>
              ) : null}
              {local.take_profit_price ? (
                <>
                  {' '}· target{' '}
                  <span className="font-mono">{formatCurrency(local.take_profit_price)}</span>
                </>
              ) : null}
              .
              <br />
              Routes to your simulated Alpaca paper account. No real money is touched.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                approve();
              }}
              disabled={busy}
              className="gap-2"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              Approve
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Reject confirm */}
      <AlertDialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reject proposal?</AlertDialogTitle>
            <AlertDialogDescription>
              This proposal will be marked rejected and removed from your queue. The audit trail is
              preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                reject();
              }}
              disabled={busy}
              className="bg-red-600 hover:bg-red-500 text-white gap-2"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
              Reject
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
