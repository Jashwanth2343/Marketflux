import { useState } from 'react';
import { toast } from 'sonner';
import { Loader2, ShieldCheck } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import api from '@/lib/api';

export function PilotOnboarding({ open, onOpenChange, onConsented }) {
  const [paperOnly, setPaperOnly] = useState(true);
  const [notAdvice, setNotAdvice] = useState(true);
  const [auditLogging, setAuditLogging] = useState(true);
  const [killPhrase, setKillPhrase] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!paperOnly || !notAdvice || !auditLogging) {
      toast.error('Please confirm all three guardrails to continue.');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        accept_paper_only: paperOnly,
        accept_not_advice: notAdvice,
        accept_audit_logging: auditLogging,
      };
      const trimmed = killPhrase.trim();
      if (trimmed) payload.kill_phrase = trimmed;
      const res = await api.post('/pilot/consent', payload);
      toast.success('Pilot consent recorded. You are in control.');
      onConsented?.(res.data?.item || null);
      onOpenChange?.(false);
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.message ||
        'Unknown error';
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg || d.message || JSON.stringify(d)).join('; ')
        : String(detail);
      toast.error(`Could not save consent. Backend says: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="w-4 h-4 text-primary" />
            Welcome to Pilot
          </DialogTitle>
          <DialogDescription>
            Pilot trades a paper Alpaca account on your behalf within strict guardrails. You approve every trade. You
            can stop everything at any time.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="flex items-start justify-between gap-4 rounded-lg border border-border bg-card p-3">
            <div>
              <div className="text-sm font-medium text-foreground">Paper account only</div>
              <p className="text-xs text-muted-foreground mt-1">
                All proposals route to a simulated Alpaca paper account. No real funds are touched.
              </p>
            </div>
            <Switch checked={paperOnly} onCheckedChange={setPaperOnly} />
          </div>

          <div className="flex items-start justify-between gap-4 rounded-lg border border-border bg-card p-3">
            <div>
              <div className="text-sm font-medium text-foreground">Not financial advice</div>
              <p className="text-xs text-muted-foreground mt-1">
                Pilot output is research, not advice. You are responsible for every approval.
              </p>
            </div>
            <Switch checked={notAdvice} onCheckedChange={setNotAdvice} />
          </div>

          <div className="flex items-start justify-between gap-4 rounded-lg border border-border bg-card p-3">
            <div>
              <div className="text-sm font-medium text-foreground">Audit logging</div>
              <p className="text-xs text-muted-foreground mt-1">
                Every proposal, approval, and execution is logged so you can review later.
              </p>
            </div>
            <Switch checked={auditLogging} onCheckedChange={setAuditLogging} />
          </div>

          <div className="space-y-2 pt-1">
            <Label htmlFor="pilot-kill-phrase" className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
              Kill phrase (optional)
            </Label>
            <Input
              id="pilot-kill-phrase"
              placeholder="e.g. stop atlas now"
              value={killPhrase}
              onChange={(e) => setKillPhrase(e.target.value)}
              autoComplete="off"
            />
            <p className="text-[11px] text-muted-foreground">
              Typing this phrase in chat will halt every Pilot personality instantly.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange?.(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={submitting} className="gap-2">
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Grant consent
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
