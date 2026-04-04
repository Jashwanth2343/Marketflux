import { useState, useEffect, useRef, useMemo } from 'react';
import DOMPurify from 'dompurify';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Briefcase, Plus, Trash2, BarChart3, Loader2, Lock, Upload, Image, CheckSquare, X, TrendingUp, TrendingDown, DollarSign, PieChart as PieChartIcon } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '@/lib/api';

function formatPrice(val) {
  if (!val && val !== 0) return '--';
  return Number(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function renderMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/^### (.*$)/gm, '<h3>$1</h3>')
    .replace(/^## (.*$)/gm, '<h2>$1</h2>')
    .replace(/^# (.*$)/gm, '<h1>$1</h1>')
    .replace(/^\- (.*$)/gm, '<li>$1</li>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>');
}

const DONUT_COLORS = ['#00FF41', '#00F3FF', '#FFB000', '#FF3333', '#8B5CF6', '#F472B6', '#34D399', '#FBBF24', '#60A5FA', '#C084FC'];

export default function Portfolio() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [holdings, setHoldings] = useState(() => {
    try {
      const saved = localStorage.getItem('fluxai_portfolio');
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });

  useEffect(() => {
    localStorage.setItem('fluxai_portfolio', JSON.stringify(holdings));
  }, [holdings]);

  const [newTicker, setNewTicker] = useState('');
  const [newShares, setNewShares] = useState('');
  const [newAvgPrice, setNewAvgPrice] = useState('');
  const [analysis, setAnalysis] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [saving, setSaving] = useState(false);

  // Real-time prices
  const [prices, setPrices] = useState({});
  const [pricesLoading, setPricesLoading] = useState(false);
  const [pricesUnavailable, setPricesUnavailable] = useState(false);

  // Image upload
  const [uploadImage, setUploadImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [parsing, setParsing] = useState(false);
  const [parsedHoldings, setParsedHoldings] = useState([]);
  const [parseError, setParseError] = useState(null);
  const [selectedParsed, setSelectedParsed] = useState([]);
  const fileInputRef = useRef(null);

  // Fetch real-time prices when holdings change
  useEffect(() => {
    const fetchPrices = async () => {
      if (holdings.length === 0) {
        setPrices({});
        setPricesUnavailable(false);
        return;
      }
      setPricesLoading(true);
      setPricesUnavailable(false);
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      try {
        const tickers = holdings.map(h => h.ticker).join(',');
        const res = await api.get(`/portfolio-prices?tickers=${tickers}`, { signal: controller.signal });
        setPrices(res.data);
      } catch (err) {
        console.error('Price fetch error:', err);
        setPricesUnavailable(true);
      } finally {
        clearTimeout(timeoutId);
        setPricesLoading(false);
      }
    };
    fetchPrices();
  }, [holdings]);

  const { enrichedHoldings, totalInvested, totalCurrentValue, totalPL, totalPLPercent, todayChangeTotal, donutData } = useMemo(() => {
    const totalInvested = holdings.reduce((sum, h) => sum + h.shares * h.avg_price, 0);

    const enrichedHoldings = holdings.map(h => {
      const p = prices[h.ticker] || {};
      const currentPrice = p.price || 0;
      const currentValue = currentPrice * h.shares;
      const costBasis = h.shares * h.avg_price;
      const plDollar = currentValue - costBasis;
      const plPercent = costBasis > 0 ? (plDollar / costBasis) * 100 : 0;
      const todayChange = p.change_percent || 0;
      return { ...h, currentPrice, currentValue, costBasis, plDollar, plPercent, todayChange };
    });

    const totalCurrentValue = enrichedHoldings.reduce((sum, h) => sum + h.currentValue, 0);
    const totalPL = totalCurrentValue - totalInvested;
    const totalPLPercent = totalInvested > 0 ? (totalPL / totalInvested) * 100 : 0;
    const todayChangeTotal = enrichedHoldings.reduce((sum, h) => {
      return sum + (h.currentPrice * h.shares * (h.todayChange / 100));
    }, 0);

    const donutData = enrichedHoldings
      .filter(h => h.currentValue > 0)
      .map(h => ({
        name: h.ticker,
        value: h.currentValue,
      }));

    return { enrichedHoldings, totalInvested, totalCurrentValue, totalPL, totalPLPercent, todayChangeTotal, donutData };
  }, [holdings, prices]);

  if (!user) {
    return (
      <div className="p-6 grid-bg min-h-screen flex items-center justify-center" data-testid="portfolio-page">
        <Card className="rounded-none border-border dark:bg-card/50 bg-card max-w-md w-full">
          <CardContent className="p-8 text-center">
            <Lock className="w-8 h-8 text-primary mx-auto mb-4" />
            <h2 className="font-mono text-lg text-foreground uppercase tracking-wider mb-2">Login Required</h2>
            <p className="text-xs text-muted-foreground mb-4">Portfolio management requires authentication</p>
            <Button
              data-testid="portfolio-login-btn"
              onClick={() => navigate('/auth')}
              className="rounded-none bg-primary text-black font-mono text-xs uppercase tracking-wider hover:bg-primary/80"
            >
              Login to Continue
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const addHolding = () => {
    if (!newTicker || !newShares || !newAvgPrice) return;
    const holding = {
      ticker: newTicker.toUpperCase(),
      shares: parseFloat(newShares),
      avg_price: parseFloat(newAvgPrice),
    };
    setHoldings(prev => [...prev, holding]);
    setNewTicker('');
    setNewShares('');
    setNewAvgPrice('');
  };

  const removeHolding = (index) => {
    setHoldings(prev => prev.filter((_, i) => i !== index));
  };

  const savePortfolio = async () => {
    setSaving(true);
    try {
      await api.post('/portfolio', { holdings });
    } catch { }
    setSaving(false);
  };

  const rebalance = async () => {
    if (holdings.length === 0) return;
    setAnalyzing(true);
    setAnalysis('');
    try {
      const res = await api.post('/portfolio/rebalance', { holdings });
      setAnalysis(res.data.analysis);
    } catch (err) {
      setAnalysis('Failed to analyze portfolio. Please try again.');
    }
    setAnalyzing(false);
  };

  // Image upload handlers
  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploadImage(file);
    setImagePreview(URL.createObjectURL(file));
    setParsedHoldings([]);
    setSelectedParsed([]);
  };

  const parseImage = async () => {
    if (!uploadImage) return;
    setParsing(true);
    setParseError(null);
    try {
      const formData = new FormData();
      formData.append('file', uploadImage);
      const res = await api.post('/parse-portfolio-image', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (res.data.success === false) {
        setParseError(res.data.error || 'Failed to parse image.');
        setParsedHoldings([]);
        return;
      }
      const parsed = res.data.holdings || [];
      setParsedHoldings(parsed);
      setSelectedParsed(parsed.map((_, i) => i));
    } catch (err) {
      console.error('Parse error:', err);
      setParseError(err.response?.data?.error || err.message || 'Error connecting to server.');
      setParsedHoldings([]);
    } finally {
      setParsing(false);
    }
  };

  const addParsedHoldings = () => {
    const toAdd = selectedParsed.map(i => ({
      ticker: parsedHoldings[i].ticker.toUpperCase(),
      shares: parsedHoldings[i].shares || 0,
      avg_price: parsedHoldings[i].avgPrice || 0,
    }));
    setHoldings(prev => [...prev, ...toAdd]);
    // Clean up
    setUploadImage(null);
    setImagePreview(null);
    setParsedHoldings([]);
    setSelectedParsed([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const toggleParsedSelection = (index) => {
    setSelectedParsed(prev =>
      prev.includes(index) ? prev.filter(i => i !== index) : [...prev, index]
    );
  };

  return (
    <div className="p-4 lg:p-6 space-y-4 grid-bg min-h-screen" data-testid="portfolio-page">
      <div>
        <h1 className="text-xl md:text-3xl font-bold tracking-tighter uppercase text-foreground">
          <Briefcase className="w-6 h-6 inline mr-2 text-secondary" />
          Portfolio <span className="text-secondary glow-text-cyan">Manager</span>
        </h1>
        <p className="text-xs font-mono text-muted-foreground mt-1">
          Track holdings and get AI-powered rebalancing insights
        </p>
      </div>

      {/* Summary Cards */}
      {holdings.length > 0 && (
        <div className="space-y-2">
          {pricesUnavailable && (
            <div className="rounded-none border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] font-mono text-amber-200">
              ⚠ Price feed unavailable. Showing cached/last known values where possible.
            </div>
          )}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Card className="rounded-none border-border dark:bg-card/50 bg-card">
            <CardContent className="p-4">
              <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-1">Total Value</div>
              <div className="font-data text-xl text-foreground">
                {pricesLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : `$${formatPrice(totalCurrentValue)}`}
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-none border-border dark:bg-card/50 bg-card">
            <CardContent className="p-4">
              <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-1">Total Gain/Loss</div>
              <div className={`font-data text-xl flex items-center gap-1 ${totalPL >= 0 ? 'dark:text-[#00FF41] text-[#059669]' : 'text-[#FF3333]'}`}>
                {pricesLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : (
                  <>
                    {totalPL >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                    {totalPL >= 0 ? '+' : ''}${formatPrice(totalPL)}
                    <span className="text-xs ml-1">({totalPLPercent >= 0 ? '+' : ''}{totalPLPercent.toFixed(2)}%)</span>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-none border-border dark:bg-card/50 bg-card">
            <CardContent className="p-4">
              <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-1">Today's Change</div>
              <div className={`font-data text-xl ${todayChangeTotal >= 0 ? 'dark:text-[#00FF41] text-[#059669]' : 'text-[#FF3333]'}`}>
                {pricesLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : `${todayChangeTotal >= 0 ? '+' : ''}$${formatPrice(todayChangeTotal)}`}
              </div>
            </CardContent>
          </Card>
          <Card className="rounded-none border-border dark:bg-card/50 bg-card">
            <CardContent className="p-4">
              <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-1">Holdings</div>
              <div className="font-data text-xl text-foreground">{holdings.length}</div>
            </CardContent>
          </Card>
        </div>
        </div>
      )}

      {/* Portfolio Allocation Donut + Add Holding */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Add Holding + Upload */}
        <Card className="rounded-none border-border dark:bg-card/50 bg-card lg:col-span-2">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
              <Plus className="w-4 h-4 text-primary" /> Add Holding
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-3">
            <div className="flex flex-wrap gap-2">
              <Input
                data-testid="portfolio-ticker-input"
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value)}
                placeholder="Ticker (e.g. AAPL)"
                className="w-32 rounded-none bg-background border-border font-mono text-xs"
              />
              <Input
                data-testid="portfolio-shares-input"
                value={newShares}
                onChange={(e) => setNewShares(e.target.value)}
                placeholder="Shares"
                type="number"
                className="w-28 rounded-none bg-background border-border font-mono text-xs"
              />
              <Input
                data-testid="portfolio-avgprice-input"
                value={newAvgPrice}
                onChange={(e) => setNewAvgPrice(e.target.value)}
                placeholder="Avg Price"
                type="number"
                step="0.01"
                className="w-28 rounded-none bg-background border-border font-mono text-xs"
              />
              <Button
                data-testid="portfolio-add-btn"
                onClick={addHolding}
                className="rounded-none bg-primary text-black font-mono text-xs uppercase tracking-wider hover:bg-primary/80"
              >
                <Plus className="w-3 h-3 mr-1" /> Add
              </Button>
            </div>

            {/* Image Upload */}
            <div className="border-t border-border pt-3">
              <div className="flex items-center gap-2 mb-2">
                <Upload className="w-3.5 h-3.5 text-[#FFB000]" />
                <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">Upload Portfolio Screenshot</span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleImageSelect}
                  className="hidden"
                  id="portfolio-image-upload"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-none border-[#FFB000]/30 text-[#FFB000] font-mono text-xs uppercase hover:bg-[#FFB000]/10"
                >
                  <Image className="w-3 h-3 mr-1.5" /> Choose Image
                </Button>
                {uploadImage && (
                  <>
                    <span className="text-[10px] font-mono text-muted-foreground truncate max-w-[150px]">{uploadImage.name}</span>
                    <Button
                      size="sm"
                      onClick={parseImage}
                      disabled={parsing}
                      className="rounded-none bg-[#FFB000] text-black font-mono text-xs uppercase hover:bg-[#FFB000]/80 disabled:opacity-50"
                    >
                      {parsing ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
                      {parsing ? 'Parsing...' : 'Parse Holdings'}
                    </Button>
                    <button onClick={() => { setUploadImage(null); setImagePreview(null); setParsedHoldings([]); setParseError(null); if (fileInputRef.current) fileInputRef.current.value = ''; }}>
                      <X className="w-3.5 h-3.5 text-muted-foreground hover:text-destructive" />
                    </button>
                  </>
                )}
              </div>

              {parseError && (
                <div className="text-red-500 font-mono text-xs mt-2">
                  {parseError}
                </div>
              )}

              {imagePreview && (
                <div className="mt-2 border border-border p-1 inline-block">
                  <img src={imagePreview} alt="Portfolio" className="max-h-32 object-contain" />
                </div>
              )}

              {/* Parsed Results */}
              {parsedHoldings.length > 0 && (
                <div className="mt-3 border border-[#FFB000]/30 bg-[#FFB000]/5 p-3 space-y-2">
                  <div className="text-[10px] font-mono text-[#FFB000] uppercase tracking-wider">
                    Parsed {parsedHoldings.length} holdings from image
                  </div>
                  <table className="w-full text-[10px] font-mono">
                    <thead>
                      <tr className="border-b border-[#FFB000]/20 text-muted-foreground">
                        <th className="text-left py-1 pr-2 w-6"></th>
                        <th className="text-left py-1 pr-2">Ticker</th>
                        <th className="text-right py-1 pr-2">Shares</th>
                        <th className="text-right py-1">Avg Price</th>
                      </tr>
                    </thead>
                    <tbody>
                      {parsedHoldings.map((ph, i) => (
                        <tr key={i} className="border-b border-[#FFB000]/10">
                          <td className="py-1 pr-2">
                            <input
                              type="checkbox"
                              checked={selectedParsed.includes(i)}
                              onChange={() => toggleParsedSelection(i)}
                              className="accent-[#FFB000]"
                            />
                          </td>
                          <td className="py-1 pr-2 text-foreground font-bold">{ph.ticker}</td>
                          <td className="py-1 pr-2 text-right text-foreground">{ph.shares}</td>
                          <td className="py-1 text-right text-foreground">${formatPrice(ph.avgPrice)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <Button
                    size="sm"
                    onClick={addParsedHoldings}
                    disabled={selectedParsed.length === 0}
                    className="rounded-none bg-[#FFB000] text-black font-mono text-xs uppercase hover:bg-[#FFB000]/80"
                  >
                    <CheckSquare className="w-3 h-3 mr-1" /> Add Selected ({selectedParsed.length})
                  </Button>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Donut Chart */}
        {donutData.length > 0 && (
          <Card className="rounded-none border-border dark:bg-card/50 bg-card">
            <CardHeader className="pb-2 pt-3 px-4">
              <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
                <PieChartIcon className="w-4 h-4 text-primary" /> Allocation
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3">
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={donutData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {donutData.map((_, index) => (
                      <Cell key={index} fill={DONUT_COLORS[index % DONUT_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => `$${formatPrice(value)}`}
                    contentStyle={{ background: '#0A0A0A', border: '1px solid #1E293B', borderRadius: 0, fontFamily: 'JetBrains Mono', fontSize: '10px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2">
                {donutData.map((d, i) => (
                  <div key={d.name} className="flex items-center gap-1 text-[9px] font-mono">
                    <div className="w-2 h-2" style={{ backgroundColor: DONUT_COLORS[i % DONUT_COLORS.length] }} />
                    <span className="text-muted-foreground">{d.name}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Holdings Table */}
      {holdings.length > 0 && (
        <Card className="rounded-none border-border dark:bg-card/50 bg-card">
          <CardHeader className="pb-2 pt-3 px-4 flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-mono uppercase tracking-wider">
              Holdings ({holdings.length})
            </CardTitle>
            <div className="flex gap-2">
              <Button
                data-testid="portfolio-save-btn"
                variant="outline"
                size="sm"
                onClick={savePortfolio}
                disabled={saving}
                className="rounded-none border-border font-mono text-xs uppercase hover:bg-primary hover:text-black"
              >
                {saving ? 'Saving...' : 'Save'}
              </Button>
              <Button
                data-testid="portfolio-rebalance-btn"
                size="sm"
                onClick={rebalance}
                disabled={analyzing}
                className="rounded-none bg-secondary text-black font-mono text-xs uppercase tracking-wider hover:bg-secondary/80"
              >
                {analyzing ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <BarChart3 className="w-3 h-3 mr-1" />}
                AI Rebalance
              </Button>
            </div>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-border">
                    <TableHead className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Ticker</TableHead>
                    <TableHead className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground text-right">Shares</TableHead>
                    <TableHead className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground text-right">Avg Price</TableHead>
                    <TableHead className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground text-right">Current</TableHead>
                    <TableHead className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground text-right">Value</TableHead>
                    <TableHead className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground text-right">P&L ($)</TableHead>
                    <TableHead className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground text-right">P&L (%)</TableHead>
                    <TableHead className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground text-right hidden sm:table-cell">Today</TableHead>
                    <TableHead className="w-8"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {enrichedHoldings.map((h, i) => (
                    <TableRow key={i} className="border-border" data-testid={`holding-row-${i}`}>
                      <TableCell className="font-mono font-bold text-foreground">{h.ticker}</TableCell>
                      <TableCell className="font-data text-foreground text-right">{h.shares}</TableCell>
                      <TableCell className="font-data text-foreground text-right">${formatPrice(h.avg_price)}</TableCell>
                      <TableCell className="font-data text-foreground text-right">
                        {pricesLoading ? <Loader2 className="w-3 h-3 animate-spin inline" /> : h.currentPrice ? `$${formatPrice(h.currentPrice)}` : '--'}
                      </TableCell>
                      <TableCell className="font-data text-foreground text-right">
                        {h.currentValue ? `$${formatPrice(h.currentValue)}` : '--'}
                      </TableCell>
                      <TableCell className={`font-data text-right ${h.plDollar >= 0 ? 'dark:text-[#00FF41] text-[#059669]' : 'text-[#FF3333]'}`}>
                        {h.currentPrice ? `${h.plDollar >= 0 ? '+' : ''}$${formatPrice(h.plDollar)}` : '--'}
                      </TableCell>
                      <TableCell className={`font-data text-right ${h.plPercent >= 0 ? 'dark:text-[#00FF41] text-[#059669]' : 'text-[#FF3333]'}`}>
                        {h.currentPrice ? `${h.plPercent >= 0 ? '+' : ''}${h.plPercent.toFixed(2)}%` : '--'}
                      </TableCell>
                      <TableCell className={`font-data text-right hidden sm:table-cell ${h.todayChange >= 0 ? 'dark:text-[#00FF41] text-[#059669]' : 'text-[#FF3333]'}`}>
                        {h.currentPrice ? `${h.todayChange >= 0 ? '+' : ''}${h.todayChange.toFixed(2)}%` : '--'}
                      </TableCell>
                      <TableCell>
                        <button data-testid={`remove-holding-${i}`} onClick={() => removeHolding(i)}>
                          <Trash2 className="w-3 h-3 text-muted-foreground hover:text-destructive" />
                        </button>
                      </TableCell>
                    </TableRow>
                  ))}
                  <TableRow className="border-border font-bold">
                    <TableCell className="font-mono text-foreground">TOTAL</TableCell>
                    <TableCell></TableCell>
                    <TableCell className="font-data text-muted-foreground text-right">${formatPrice(totalInvested)}</TableCell>
                    <TableCell></TableCell>
                    <TableCell className="font-data text-primary text-right">${formatPrice(totalCurrentValue)}</TableCell>
                    <TableCell className={`font-data text-right ${totalPL >= 0 ? 'dark:text-[#00FF41] text-[#059669]' : 'text-[#FF3333]'}`}>
                      {totalPL >= 0 ? '+' : ''}${formatPrice(totalPL)}
                    </TableCell>
                    <TableCell className={`font-data text-right ${totalPLPercent >= 0 ? 'dark:text-[#00FF41] text-[#059669]' : 'text-[#FF3333]'}`}>
                      {totalPLPercent >= 0 ? '+' : ''}{totalPLPercent.toFixed(2)}%
                    </TableCell>
                    <TableCell className="hidden sm:table-cell"></TableCell>
                    <TableCell></TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* AI Analysis */}
      {analyzing && (
        <Card className="rounded-none border-secondary/30 bg-secondary/5">
          <CardContent className="p-6 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-secondary mx-auto mb-3" />
            <p className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
              AI is analyzing your portfolio<span className="cursor-blink">_</span>
            </p>
          </CardContent>
        </Card>
      )}

      {analysis && !analyzing && (
        <Card className="rounded-none border-secondary/30 dark:bg-card/50 bg-card">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-sm font-mono uppercase tracking-wider flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-secondary" /> AI Portfolio Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div
              className="markdown-content text-sm leading-relaxed text-foreground"
              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(renderMarkdown(analysis)) }}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
