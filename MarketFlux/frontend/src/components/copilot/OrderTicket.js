import { useState } from 'react';
import { Loader2, ArrowUpCircle, ArrowDownCircle, ShieldCheck, Ticket } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import alpacaApi from '@/lib/alpacaApi';

const inputCls =
  'h-9 w-full rounded-lg border border-border bg-background px-3 font-mono text-sm text-foreground outline-none focus:border-primary/50';

export default function OrderTicket({ onSubmitted }) {
  const [symbol, setSymbol] = useState('');
  const [side, setSide] = useState('buy');
  const [qty, setQty] = useState('');
  const [orderType, setOrderType] = useState('market');
  const [limitPrice, setLimitPrice] = useState('');
  const [tif, setTif] = useState('day');
  const [reviewing, setReviewing] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const valid =
    symbol.trim().length > 0 &&
    Number(qty) > 0 &&
    (orderType === 'market' || Number(limitPrice) > 0);

  const submit = async () => {
    if (!valid || submitting) return;
    setSubmitting(true);
    try {
      const payload = {
        symbol: symbol.trim().toUpperCase(),
        qty: Number(qty),
        side,
        order_type: orderType,
        time_in_force: tif,
        ...(orderType === 'limit' ? { limit_price: Number(limitPrice) } : {}),
      };
      const res = await alpacaApi.submitOrder(payload);
      toast.success(
        `${side === 'buy' ? 'Buy' : 'Sell'} ${qty} ${payload.symbol} submitted`,
        { description: `Paper account · status: ${res?.status || 'accepted'}` }
      );
      setReviewing(false);
      setSymbol('');
      setQty('');
      setLimitPrice('');
      onSubmitted?.(res);
    } catch (err) {
      toast.error('Order rejected', {
        description:
          err?.response?.data?.detail || err?.message || 'Broker refused the order',
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl rounded-2xl border border-white/10 bg-white/[0.025] p-5 shadow-xl shadow-black/25 backdrop-blur">
      <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-foreground">
        <Ticket className="h-4 w-4 text-primary" />
        Manual order ticket
      </div>
      <div className="mb-4 flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <ShieldCheck className="h-3.5 w-3.5 text-primary" />
        Paper trading only — no real money moves.
      </div>

      {!reviewing ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Symbol</label>
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase().replace(/[^A-Z.]/g, ''))}
              placeholder="AAPL"
              className={inputCls}
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Side</label>
            <div className="grid h-9 grid-cols-2 gap-1 rounded-lg border border-border p-1">
              {['buy', 'sell'].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setSide(s)}
                  className={`flex items-center justify-center gap-1 rounded-md text-xs font-semibold transition-colors ${
                    side === s
                      ? s === 'buy'
                        ? 'bg-primary/20 text-primary'
                        : 'bg-amber-500/20 text-amber-400'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {s === 'buy' ? <ArrowUpCircle className="h-3.5 w-3.5" /> : <ArrowDownCircle className="h-3.5 w-3.5" />}
                  {s === 'buy' ? 'Buy' : 'Sell'}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Quantity</label>
            <input
              value={qty}
              onChange={(e) => setQty(e.target.value.replace(/[^0-9.]/g, ''))}
              placeholder="10"
              inputMode="decimal"
              className={inputCls}
            />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Order type</label>
            <div className="grid h-9 grid-cols-2 gap-1 rounded-lg border border-border p-1">
              {['market', 'limit'].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setOrderType(t)}
                  className={`rounded-md text-xs font-semibold capitalize transition-colors ${
                    orderType === t ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          {orderType === 'limit' && (
            <div>
              <label className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Limit price ($)</label>
              <input
                value={limitPrice}
                onChange={(e) => setLimitPrice(e.target.value.replace(/[^0-9.]/g, ''))}
                placeholder="150.00"
                inputMode="decimal"
                className={inputCls}
              />
            </div>
          )}
          <div>
            <label className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Time in force</label>
            <select value={tif} onChange={(e) => setTif(e.target.value)} className={inputCls}>
              <option value="day">Day</option>
              <option value="gtc">Good-til-cancelled</option>
              <option value="ioc">Immediate-or-cancel</option>
              <option value="fok">Fill-or-kill</option>
            </select>
          </div>
          <div className="sm:col-span-2">
            <Button
              onClick={() => setReviewing(true)}
              disabled={!valid}
              className="h-9 w-full rounded-lg text-xs font-semibold"
            >
              Review order
            </Button>
          </div>
        </div>
      ) : (
        <div>
          <div className="rounded-xl border border-border bg-card/60 p-4 font-mono text-sm">
            <div className="flex items-center gap-2">
              {side === 'buy' ? <ArrowUpCircle className="h-5 w-5 text-primary" /> : <ArrowDownCircle className="h-5 w-5 text-amber-400" />}
              <span className="font-bold capitalize">{side}</span>
              <span>{qty} × {symbol.trim().toUpperCase()}</span>
            </div>
            <div className="mt-2 space-y-1 text-xs text-muted-foreground">
              <div>Type: <span className="text-foreground capitalize">{orderType}</span>
                {orderType === 'limit' && <span className="text-foreground"> @ ${limitPrice}</span>}</div>
              <div>Time in force: <span className="text-foreground uppercase">{tif}</span></div>
              <div>Account: <span className="text-foreground">Paper (Alpaca)</span></div>
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <Button
              onClick={submit}
              disabled={submitting}
              className="h-9 flex-1 gap-1.5 rounded-lg text-xs font-semibold"
            >
              {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />}
              Confirm — submit paper order
            </Button>
            <Button
              variant="outline"
              onClick={() => setReviewing(false)}
              disabled={submitting}
              className="h-9 rounded-lg text-xs"
            >
              Back
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
