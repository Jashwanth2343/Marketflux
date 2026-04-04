import { useMemo, useState } from 'react';
import { ArrowLeft, CheckCircle2, Loader2, Lock, ShieldCheck, Sparkles, Target } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { useAuth } from '@/contexts/AuthContext';
import thesisApi from '@/lib/thesisApi';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const horizonOptions = [
  { value: 'short_term', label: 'Short term' },
  { value: 'medium_term', label: 'Medium term' },
  { value: 'long_term', label: 'Long term' },
];

function parseInvalidationConditions(text) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

export default function ThesisNew() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const [ticker, setTicker] = useState('');
  const [timeHorizon, setTimeHorizon] = useState('medium_term');
  const [claim, setClaim] = useState('');
  const [whyNow, setWhyNow] = useState('');
  const [invalidationText, setInvalidationText] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const invalidationCount = useMemo(
    () => parseInvalidationConditions(invalidationText).length,
    [invalidationText],
  );

  if (loading) {
    return (
      <div className="thesis-shell p-6 flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="thesis-shell p-6 flex min-h-screen items-center justify-center">
        <Card className="thesis-panel w-full max-w-md border-white/10">
          <CardContent className="p-8 text-center">
            <Lock className="mx-auto mb-4 h-9 w-9 text-primary" />
            <h2 className="text-xl font-semibold text-foreground">Login required</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Thesis creation is tied to your private workspace, memos, and simulated trading policies.
            </p>
            <Button className="mt-6" onClick={() => navigate('/auth')}>
              Continue to login
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!ticker.trim() || !claim.trim()) {
      toast.error('Ticker and claim are required.');
      return;
    }

    setSubmitting(true);
    try {
      const res = await thesisApi.createThesis({
        ticker: ticker.trim().toUpperCase(),
        time_horizon: timeHorizon,
        claim: claim.trim(),
        why_now: whyNow.trim(),
        invalidation_conditions: parseInvalidationConditions(invalidationText),
      });
      const thesisId = res.item?.thesis?.id;
      toast.success('Thesis created. Evidence collection is running in the background.');
      navigate(`/theses/${thesisId}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Unable to create thesis right now.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="thesis-shell min-h-screen p-4 md:p-6 lg:p-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="thesis-kicker">Thesis OS composer</div>
            <h1 className="thesis-display mt-2 text-4xl font-semibold text-foreground">Create a living thesis</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground">
              Define the claim in plain language, capture what would make you wrong, and let MarketFlux attach the first wave of evidence blocks automatically.
            </p>
          </div>
          <Button asChild variant="outline" className="rounded-full border-white/10 bg-white/5 text-foreground hover:bg-white/10">
            <Link to="/theses">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to library
            </Link>
          </Button>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <Card className="thesis-panel rounded-[28px] border-white/10">
            <CardHeader>
              <CardDescription className="thesis-kicker">Primary input</CardDescription>
              <CardTitle className="text-2xl font-semibold text-foreground">Research claim</CardTitle>
            </CardHeader>
            <CardContent>
              <form className="space-y-5" onSubmit={handleSubmit} data-testid="thesis-new-form">
                <div className="grid gap-5 md:grid-cols-[0.35fr_0.65fr]">
                  <div className="space-y-2">
                    <label className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground">Ticker</label>
                    <Input
                      value={ticker}
                      onChange={(event) => setTicker(event.target.value.toUpperCase())}
                      placeholder="NVDA"
                      className="h-11 border-white/10 bg-black/20 font-mono text-base"
                      data-testid="thesis-ticker-input"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground">Time horizon</label>
                    <Select value={timeHorizon} onValueChange={setTimeHorizon}>
                      <SelectTrigger className="h-11 border-white/10 bg-black/20">
                        <SelectValue placeholder="Select horizon" />
                      </SelectTrigger>
                      <SelectContent>
                        {horizonOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground">Claim</label>
                  <Textarea
                    value={claim}
                    onChange={(event) => setClaim(event.target.value)}
                    placeholder="Example: NVDA can sustain premium data-center growth through the next 12 months because AI capex remains supply-constrained and software monetization is widening."
                    className="min-h-[140px] border-white/10 bg-black/20 text-sm leading-6"
                    data-testid="thesis-claim-input"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground">Why now</label>
                  <Textarea
                    value={whyNow}
                    onChange={(event) => setWhyNow(event.target.value)}
                    placeholder="What changed in the market, company, or regime that makes this thesis timely?"
                    className="min-h-[120px] border-white/10 bg-black/20 text-sm leading-6"
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <label className="text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground">Invalidation conditions</label>
                    <span className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
                      {invalidationCount} condition{invalidationCount === 1 ? '' : 's'}
                    </span>
                  </div>
                  <Textarea
                    value={invalidationText}
                    onChange={(event) => setInvalidationText(event.target.value)}
                    placeholder={'One condition per line\nGross margins compress below plan\nAI infrastructure orders slow materially\nCapex spending guidance is cut'}
                    className="min-h-[140px] border-white/10 bg-black/20 text-sm leading-6"
                  />
                </div>

                <div className="flex flex-wrap items-center gap-3 pt-2">
                  <Button type="submit" disabled={submitting} className="rounded-full px-6">
                    {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Create thesis
                  </Button>
                  <p className="text-sm text-muted-foreground">
                    Filing, news, macro, and price-action evidence will start collecting right after save.
                  </p>
                </div>
              </form>
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card className="thesis-panel rounded-[28px] border-white/10">
              <CardHeader>
                <CardDescription className="thesis-kicker">Quality bar</CardDescription>
                <CardTitle className="text-2xl font-semibold text-foreground">What makes a strong thesis?</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm leading-7 text-muted-foreground">
                <div className="rounded-2xl border border-emerald-400/15 bg-emerald-400/10 p-4">
                  <div className="flex items-center gap-2 text-emerald-200">
                    <Target className="h-4 w-4" />
                    <span className="font-medium">Specific upside claim</span>
                  </div>
                  <p className="mt-2">
                    Name the mechanism you believe the market is underpricing, not just the direction you like.
                  </p>
                </div>
                <div className="rounded-2xl border border-cyan-400/15 bg-cyan-400/10 p-4">
                  <div className="flex items-center gap-2 text-cyan-200">
                    <Sparkles className="h-4 w-4" />
                    <span className="font-medium">Fresh trigger</span>
                  </div>
                  <p className="mt-2">
                    Explain why the next few weeks or quarters matter. The evidence engine can only help if the claim is time-aware.
                  </p>
                </div>
                <div className="rounded-2xl border border-amber-400/15 bg-amber-400/10 p-4">
                  <div className="flex items-center gap-2 text-amber-200">
                    <ShieldCheck className="h-4 w-4" />
                    <span className="font-medium">Clear invalidation</span>
                  </div>
                  <p className="mt-2">
                    If you cannot write down what breaks the idea, you cannot safely connect it to memo generation or paper trades.
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card className="thesis-panel rounded-[28px] border-white/10">
              <CardHeader>
                <CardDescription className="thesis-kicker">What happens next</CardDescription>
                <CardTitle className="text-2xl font-semibold text-foreground">Automatic evidence loop</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm leading-7 text-muted-foreground">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-1 h-4 w-4 text-primary" />
                  <p>MarketFlux creates the initial revision and stores your claim in Postgres as the canonical thesis object.</p>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-1 h-4 w-4 text-primary" />
                  <p>Background collection starts for filings, price action, macro regime context, and recent news.</p>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-1 h-4 w-4 text-primary" />
                  <p>You can then revise the thesis, generate a memo, and move into the paper-trade lab with policy checks.</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
