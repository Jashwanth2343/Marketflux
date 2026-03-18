import { useEffect, useState, useCallback, useRef } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search, RefreshCw, Filter } from 'lucide-react';
import NewsCard from '@/components/NewsCard';
import api from '@/lib/api';

export default function NewsFeed() {
  const [articles, setArticles] = useState([]);
  const [keyword, setKeyword] = useState('');
  const [sentimentFilter, setSentimentFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
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
      if (mountedRef.current) setLoading(false);
    }
  }, [keyword, sentimentFilter, categoryFilter, watchlistOnly]);

  useEffect(() => { fetchNews(1); }, [fetchNews]);

  const handleSearch = (e) => {
    e.preventDefault();
    fetchNews(1);
  };

  const refreshNews = async () => {
    try {
      await api.post('/news/refresh');
      setTimeout(() => fetchNews(1), 2000);
    } catch { }
  };

  const sentimentOptions = ['', 'bullish', 'bearish', 'neutral'];
  const categoryOptions = ['', 'general', 'technology', 'finance', 'world'];

  return (
    <div className="p-4 lg:p-6 space-y-4 grid-bg min-h-screen" data-testid="news-feed-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl md:text-3xl font-bold tracking-tighter uppercase text-foreground">
            News <span className="text-secondary glow-text-cyan">Feed</span>
          </h1>
          <p className="text-xs font-mono text-muted-foreground mt-1">{total} articles</p>
        </div>
        <Button
          data-testid="refresh-news"
          variant="outline"
          size="sm"
          onClick={refreshNews}
          className="rounded-none border-border font-mono text-xs uppercase tracking-wider hover:bg-secondary hover:text-black"
        >
          <RefreshCw className="w-3 h-3 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Search & Filters */}
      <Card className="rounded-none border-border dark:bg-card/50 bg-card">
        <CardContent className="p-4">
          <form onSubmit={handleSearch} className="flex gap-2 mb-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                data-testid="news-search-input"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="Search headlines..."
                className="pl-10 rounded-none bg-background border-border font-mono text-sm"
              />
            </div>
            <Button
              data-testid="news-search-btn"
              type="submit"
              className="rounded-none bg-primary text-black font-mono text-xs uppercase hover:bg-primary/80"
            >
              Search
            </Button>
          </form>

          <div className="flex flex-wrap gap-2">
            <div className="flex items-center gap-1">
              <Filter className="w-3 h-3 text-muted-foreground" />
              <span className="text-[10px] font-mono text-muted-foreground uppercase mr-1">Sentiment:</span>
              {sentimentOptions.map(s => (
                <button
                  key={s || 'all'}
                  data-testid={`filter-sentiment-${s || 'all'}`}
                  onClick={() => setSentimentFilter(s)}
                  className={`px-2 py-1 text-[10px] font-mono uppercase tracking-wider border transition-colors ${sentimentFilter === s
                      ? s === 'bullish' ? 'dark:border-[#00FF41] border-[#059669] dark:text-[#00FF41] text-[#059669] dark:bg-[#00FF41] bg-[#059669]/10'
                        : s === 'bearish' ? 'border-[#FF3333] text-[#FF3333] bg-[#FF3333]/10'
                          : s === 'neutral' ? 'border-[#FFB000] text-[#FFB000] bg-[#FFB000]/10'
                            : 'border-primary text-primary bg-primary/10'
                      : 'border-border text-muted-foreground hover:border-muted-foreground/50'
                    }`}
                >
                  {s || 'All'}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1 ml-2">
              <span className="text-[10px] font-mono text-muted-foreground uppercase mr-1">Category:</span>
              {categoryOptions.map(c => (
                <button
                  key={c || 'all'}
                  data-testid={`filter-category-${c || 'all'}`}
                  onClick={() => setCategoryFilter(c)}
                  className={`px-2 py-1 text-[10px] font-mono uppercase tracking-wider border transition-colors ${categoryFilter === c
                      ? 'border-secondary text-secondary bg-secondary/10'
                      : 'border-border text-muted-foreground hover:border-muted-foreground/50'
                    }`}
                >
                  {c || 'All'}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1 ml-4 border-l border-border pl-4">
              <button
                onClick={() => setWatchlistOnly(!watchlistOnly)}
                className={`px-3 py-1 flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider border transition-all ${watchlistOnly
                    ? 'dark:border-[#00FF41] border-[#059669] dark:text-[#00FF41] text-[#059669] dark:bg-[#00FF41] bg-[#059669]/10 shadow-[0_0_10px_rgba(0,255,65,0.2)]'
                    : 'border-border text-muted-foreground hover:border-muted-foreground/50'
                  }`}
              >
                <div className={`w-2 h-2 rounded-full ${watchlistOnly ? 'dark:bg-[#00FF41] bg-[#059669] animate-pulse' : 'bg-muted-foreground'}`} />
                My Watchlist
              </button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Articles Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {articles.map((article, i) => (
          <div key={article.article_id || i} data-testid={`news-article-${i}`}>
            <NewsCard article={article} />
          </div>
        ))}
      </div>

      {loading && (
        <div className="py-8 text-center">
          <div className="w-6 h-6 border-2 border-primary border-t-transparent animate-spin mx-auto" />
        </div>
      )}

      {!loading && articles.length === 0 && (
        <div className="py-12 text-center">
          <p className="text-sm font-mono text-muted-foreground">No articles found. Try refreshing or adjusting filters.</p>
        </div>
      )}

      {hasMore && !loading && articles.length > 0 && (
        <Button
          data-testid="load-more-news"
          variant="outline"
          onClick={() => fetchNews(page + 1, true)}
          className="w-full rounded-none border-border font-mono text-xs uppercase hover:bg-primary hover:text-black"
        >
          Load More
        </Button>
      )}
    </div>
  );
}
