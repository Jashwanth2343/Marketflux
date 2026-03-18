import { ExternalLink } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function NewsCard({ article, compact = false }) {
  const hasThumbnail = !!article.thumbnail_url;

  if (compact) {
    return (
      <a
        href={article.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="group flex gap-3 p-3 border border-border dark:bg-card/50 bg-card hover:border-primary/40 transition-colors"
      >
        {hasThumbnail && (
          <div className="w-20 h-14 flex-shrink-0 overflow-hidden bg-muted">
            <img
              src={article.thumbnail_url}
              alt=""
              className="w-full h-full object-cover"
              onError={(e) => { e.target.style.display = 'none'; }}
            />
          </div>
        )}
        <div className="flex-1 min-w-0 pr-2">
          {article.tickers && article.tickers.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-1">
              {article.tickers.slice(0, 3).map(ticker => (
                <span key={ticker} className="px-1 py-0.5 rounded text-[9px] font-mono font-bold bg-primary/10 text-primary border border-primary/20">
                  {ticker}
                </span>
              ))}
            </div>
          )}
          <p className="text-sm text-foreground leading-tight line-clamp-2 group-hover:text-primary transition-colors mt-0.5">
            {article.title}
          </p>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="text-[10px] font-mono text-muted-foreground line-clamp-1">{article.source}</span>
            <span className="text-[10px] font-mono text-muted-foreground/50 whitespace-nowrap">{timeAgo(article.published_at)}</span>
          </div>
        </div>
        {article.sentiment && (
          <Badge variant="outline" className={`rounded-none text-[8px] font-mono uppercase flex-shrink-0 self-start sentiment-${article.sentiment}`}>
            {article.sentiment}
          </Badge>
        )}
      </a>
    );
  }

  return (
    <a
      href={article.source_url}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex flex-col border border-border dark:bg-card/50 bg-card hover:border-primary/40 transition-colors overflow-hidden"
    >
      {hasThumbnail && (
        <div className="w-full h-36 overflow-hidden bg-muted relative">
          <img
            src={article.thumbnail_url}
            alt=""
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            onError={(e) => { e.target.parentElement.style.display = 'none'; }}
          />
          {article.sentiment && (
            <Badge variant="outline" className={`absolute top-2 right-2 rounded-none text-[8px] font-mono uppercase sentiment-${article.sentiment} bg-black/60 backdrop-blur-sm`}>
              {article.sentiment}
            </Badge>
          )}
        </div>
      )}
      <div className="p-3 flex-1 flex flex-col">
        {article.tickers && article.tickers.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-1.5">
            {article.tickers.slice(0, 3).map(ticker => (
              <span key={ticker} className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-primary/10 text-primary border border-primary/20">
                {ticker}
              </span>
            ))}
          </div>
        )}
        <p className="text-sm text-foreground font-medium leading-tight line-clamp-2 group-hover:text-primary transition-colors mt-0.5">
          {article.title}
        </p>
        {article.summary && (
          <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2">{article.summary}</p>
        )}
        <div className="flex items-center justify-between mt-auto pt-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-muted-foreground">{article.source}</span>
            <span className="text-[10px] font-mono text-muted-foreground/50">{timeAgo(article.published_at)}</span>
          </div>
          <div className="flex items-center gap-2">
            {!hasThumbnail && article.sentiment && (
              <Badge variant="outline" className={`rounded-none text-[8px] font-mono uppercase sentiment-${article.sentiment}`}>
                {article.sentiment}
              </Badge>
            )}
            <ExternalLink className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>
      </div>
    </a>
  );
}
