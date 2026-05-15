import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, Octagon } from 'lucide-react';

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
import { Button } from '@/components/ui/button';

const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export function KillSwitchButton({
  personalityId,
  personalityName = 'Pilot',
  size = 'sm',
  variant = 'destructive',
  className = '',
  label = 'Kill',
  onKilled,
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const runKill = async () => {
    if (!personalityId) {
      toast.error('No personality selected to kill.');
      return;
    }
    setBusy(true);
    try {
      const res = await axios.post(
        `${API}/api/pilot/personalities/${personalityId}/kill`,
        {},
        { withCredentials: true }
      );
      const data = res?.data || {};
      const expired = Array.isArray(data.expired_proposal_ids) ? data.expired_proposal_ids.length : 0;
      const cancelled = Array.isArray(data.cancelled_alpaca_order_ids)
        ? data.cancelled_alpaca_order_ids.length
        : 0;
      toast.success(
        `Killed ${personalityName}. Expired ${expired} proposals, cancelled ${cancelled} orders.`
      );
      onKilled?.(data);
      setOpen(false);
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        'Unknown error';
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg || d.message || JSON.stringify(d)).join('; ')
        : String(detail);
      toast.error(`Could not kill ${personalityName}. Backend says: ${msg}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button
        type="button"
        size={size}
        variant={variant}
        className={`gap-1 font-mono text-xs uppercase tracking-wider ${className}`}
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
        disabled={busy}
      >
        <Octagon className="w-3 h-3" />
        {label}
      </Button>

      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-red-500">
              <Octagon className="w-4 h-4" />
              Kill {personalityName} now?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will pause the personality, cancel all pending Alpaca orders, and expire pending
              proposals. The action is logged and reversible by resuming the personality manually.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                runKill();
              }}
              disabled={busy}
              className="bg-red-600 hover:bg-red-500 text-white gap-2"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Octagon className="w-4 h-4" />}
              Kill {personalityName}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
