import { useEffect, useState, useCallback, useRef } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search, RefreshCw, Filter, Newspaper, Wifi, WifiOff } from 'lucide-react';
import NewsCard from '@/components/NewsCard';
import api from '@/lib/api';

const SENTIMENT_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'bullish', label: '▲ Bullish', color: '#4ADE80', bg: 'rgba(34,197,94,0.08)', border: 'rgba(34,197,94,0.25)' },
  { value: 'bearish', label: '▼ Bearish', color: '#FF4444', bg: 'rgba(255,68,68,0.08)', border: 'rgba(255,68,68,0.25)' },
  { value: 'neutral', label: '◆ Neutral', color: '#9298A6', bg: 'rgba(146,152,166,0.08)', border: 'rgba(146,152,166,0.25)' },
];

const CATEGORY_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'general', label: 'General' },
  { value: 'technology', label: 'Tech' },
  { value: 'finance', label: 'Finance' },
  { value: 'world', label: 'World' },
];

function SkeletonCard() {
  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'rgba(255,255,255,0.07)' }}
    >
      <div className="w-full h-36 skeleton-shimmer" />
      <div className="p-3.5 space-y-2.5">
        <div className="flex gap-1">
          <div className="h-4 w-12 rounded skeleton-shimmer" />
          <div className="h-4 w-10 rounded skeleton-shimmer" />
        </div>
        <div className="space-y-1.5">
          <div className="h-4 w-full rounded skeleton-shimmer" />
          <div className="h-4 w-4/5 rounded skeleton-shimmer" />
        </div>
        <div className="flex gap-2 pt-2 border-t border-[rgba(255,255,255,0.05)]">
          <div className="h-3 w-16 rounded skeleton-shimmer" />
          <div className="h-3 w-12 rounded skeleton-shimmer" />
        </div>
      </div>
    </div>
  );
}

function FilterPill({ active, label, color, bg, border, onClick, testId }) {
  return (
    <button
      data-testid={testId}
      onClick={onClick}
      className="px-3 py-1.5 rounded-full text-[11px] font-mono font-semibold tracking-wide transition-all duration-150"
      style={active && color ? {
        color, background: bg, borderColor: border,
        border: '1px solid', boxShadow: `0 0 8px ${bg}`
      } : {
        color: active ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.35)',
        background: active ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.03)',
        border: '1px solid',
        borderColor: active ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.08)',
      }}
    >
      {label}
    </button>
  );
}

export default function NewsFeed({ embedded = false }) {
  const [articles, setArticles] = useState([]);
  const [keyword, setKeyword] = useState('');
  const [sentimentFilter, setSentimentFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [initialLoad, setInitialLoad] = useState(true);
  const [total, setTotal] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => { mountedRef.current = false; };
  }, []);

  const fetchNews = useCallback(async (pageNum = 1, append = false) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: pageNum, limit: 20 });
      if (keyword) params.set('keyword', keyword);
      if (sentimentFilter) params.set('sentiment', sentimentFilter);
      if (categoryFilter) params.set('category', categoryFilter);
      if (watchlistOnly) params.set('watchlist', 'true');

      const res = await api.get(`/news/feed?${params}`);
      if (!mountedRef.current) return;
      const data = res.data;
      setArticles(prev => append ? [...prev, ...data.articles] : data.articles);
      setHasMore(data.has_more);
      setTotal(data.total);
      setPage(pageNum);
    } catch (e) {
      if (mountedRef.current) console.error('News fetch error:', e);
    } finally {
      if (mountedRef.current) {
        setLoading(false);
        setInitialLoad(false);
      }
    }
  }, [keyword, sentimentFilter, categoryFilter, watchlistOnly]);

  useEffect(() => { fetchNews(1); }, [fetchNews]);

  const handleSearch = (e) => {
    e.preventDefault();
    fetchNews(1);
  };

  const refreshNews = async () => {
    setRefreshing(true);
    try {
      await api.post('/news/refresh');
      setTimeout(() => fetchNews(1), 2000);
    } catch { }
    finally { setTimeout(() => setRefreshing(false), 2500); }
  };

  const hasActiveFilters = sentimentFilter || categoryFilter || watchlistOnly || keyword;

  const content = (
    <>
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Newspaper className="w-5 h-5 text-[#9298A6]" />
            <h1 className="text-xl md:text-2xl font-mono font-bold tracking-tight text-foreground">
              News <span style={{ color: '#9298A6', textShadow: '0 0 10px rgba(146,152,166,0.4)' }}>Feed</span>
            </h1>
          </div>
          <p className="text-[11px] font-mono text-muted-foreground">
            {total > 0 ? (
              <span>{total.toLocaleString()} articles · AI-analyzed sentiment</span>
            ) : (
              <span>Market intelligence · Real-time</span>
            )}
          </p>
        </div>

        <Button
          data-testid="refresh-news"
          variant="ghost"
          size="sm"
          onClick={refreshNews}
          disabled={refreshing}
          className="text-[11px] font-mono uppercase tracking-wider gap-1.5 h-8 px-3 transition-all"
          style={{
            color: refreshing ? '#E3B85F' : 'rgba(255,255,255,0.4)',
            border: '1px solid',
            borderColor: refreshing ? 'rgba(227,184,95,0.3)' : 'rgba(255,255,255,0.08)',
            background: refreshing ? 'rgba(227,184,95,0.05)' : 'transparent',
          }}
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>

      {/* Search + Filters */}
      <div
        className="rounded-xl p-4 space-y-3"
        style={{
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.07)',
        }}
      >
        {/* Search bar */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              data-testid="news-search-input"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="Search headlines, tickers, topics…"
              className="pl-10 h-9 text-sm font-mono rounded-lg"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.1)',
              }}
            />
          </div>
          <Button
            data-testid="news-search-btn"
            type="submit"
            size="sm"
            className="h-9 px-4 text-[11px] font-mono uppercase tracking-wider rounded-lg"
            style={{ background: '#9298A6', color: '#000' }}
          >
            Search
          </Button>
        </form>

        {/* Filter row */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 mr-1">
            <Filter className="w-3 h-3 text-muted-foreground" />
            <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">Filters</span>
          </div>

          {/* Divider */}
          <div className="h-4 w-px bg-[rgba(255,255,255,0.1)]" />

          {/* Sentiment */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {SENTIMENT_OPTIONS.map(opt => (
              <FilterPill
                key={opt.value || 'all-s'}
                testId={`filter-sentiment-${opt.value || 'all'}`}
                active={sentimentFilter === opt.value}
                label={opt.label}
                color={opt.color}
                bg={opt.bg}
                border={opt.border}
                onClick={() => setSentimentFilter(opt.value)}
              />
            ))}
          </div>

          <div className="h-4 w-px bg-[rgba(255,255,255,0.1)]" />

          {/* Category */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {CATEGORY_OPTIONS.map(opt => (
              <FilterPill
                key={opt.value || 'all-c'}
                testId={`filter-category-${opt.value || 'all'}`}
                active={categoryFilter === opt.value}
                label={opt.label}
                onClick={() => setCategoryFilter(opt.value)}
              />
            ))}
          </div>

          <div className="h-4 w-px bg-[rgba(255,255,255,0.1)]" />

          {/* Watchlist toggle */}
          <button
            onClick={() => setWatchlistOnly(!watchlistOnly)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-mono font-semibold tracking-wide transition-all duration-150"
            style={watchlistOnly ? {
              color: '#E3B85F', background: 'rgba(227,184,95,0.08)',
              border: '1px solid rgba(227,184,95,0.25)',
              boxShadow: '0 0 8px rgba(227,184,95,0.1)',
            } : {
              color: 'rgba(255,255,255,0.35)',
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${watchlistOnly ? 'bg-[#E3B85F] pulse-live' : 'bg-[rgba(255,255,255,0.2)]'}`} />
            Watchlist
          </button>

          {/* Clear all */}
          {hasActiveFilters && (
            <button
              onClick={() => {
                setSentimentFilter(''); setCategoryFilter('');
                setWatchlistOnly(false); setKeyword('');
              }}
              className="ml-auto text-[10px] font-mono text-muted-foreground hover:text-foreground underline underline-offset-2 transition-colors"
            >
              Clear all
            </button>
          )}
        </div>
      </div>

      {/* Articles Grid */}
      {initialLoad ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 9 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : articles.length === 0 ? (
        <div className="py-20 flex flex-col items-center gap-4 text-center">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center"
            style={{ background: 'rgba(146,152,166,0.07)', border: '1px solid rgba(146,152,166,0.15)' }}
          >
            {keyword || sentimentFilter || categoryFilter ? (
              <Search className="w-7 h-7" style={{ color: '#9298A6' }} />
            ) : (
              <WifiOff className="w-7 h-7" style={{ color: '#9298A6' }} />
            )}
          </div>
          <div>
            <p className="text-sm font-mono font-semibold text-foreground mb-1">
              {keyword || sentimentFilter || categoryFilter
                ? 'No articles match your filters'
                : 'No articles available'}
            </p>
            <p className="text-xs font-mono text-muted-foreground">
              {keyword || sentimentFilter || categoryFilter
                ? 'Try adjusting your search or clearing filters'
                : 'Click Refresh to pull the latest market news'}
            </p>
          </div>
          {(keyword || sentimentFilter || categoryFilter) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { setSentimentFilter(''); setCategoryFilter(''); setKeyword(''); }}
              className="text-xs font-mono text-[#9298A6] hover:bg-[rgba(146,152,166,0.06)]"
            >
              Clear filters
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {articles.map((article, i) => (
            <div key={article.article_id || i} data-testid={`news-article-${i}`}>
              <NewsCard article={article} />
            </div>
          ))}
        </div>
      )}

      {/* Loading more */}
      {loading && !initialLoad && (
        <div className="py-6 text-center">
          <div
            className="w-5 h-5 rounded-full border-2 animate-spin mx-auto"
            style={{ borderColor: 'rgba(146,152,166,0.2)', borderTopColor: '#9298A6' }}
          />
        </div>
      )}

      {/* Load More */}
      {hasMore && !loading && articles.length > 0 && (
        <Button
          data-testid="load-more-news"
          variant="ghost"
          onClick={() => fetchNews(page + 1, true)}
          className="w-full h-10 text-[11px] font-mono uppercase tracking-wider transition-all"
          style={{
            border: '1px solid rgba(255,255,255,0.08)',
            color: 'rgba(255,255,255,0.4)',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = 'rgba(146,152,166,0.25)';
            e.currentTarget.style.color = '#9298A6';
            e.currentTarget.style.background = 'rgba(146,152,166,0.04)';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
            e.currentTarget.style.color = 'rgba(255,255,255,0.4)';
            e.currentTarget.style.background = 'transparent';
          }}
        >
          Load more articles ↓
        </Button>
      )}
    </>
  );

  if (embedded) return content;

  return (
    <div className="p-4 lg:p-6 space-y-4 grid-bg min-h-screen" data-testid="news-feed-page">
      {content}
    </div>
  );
}
