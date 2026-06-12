import { ExternalLink, Clock } from 'lucide-react';

const SENTIMENT_STYLES = {
  bullish:  { color: '#4ADE80', bg: 'rgba(34,197,94,0.08)',   border: 'rgba(34,197,94,0.2)',   label: '▲ Bullish' },
  BULLISH:  { color: '#4ADE80', bg: 'rgba(34,197,94,0.08)',   border: 'rgba(34,197,94,0.2)',   label: '▲ Bullish' },
  POSITIVE: { color: '#4ADE80', bg: 'rgba(34,197,94,0.08)',   border: 'rgba(34,197,94,0.2)',   label: '▲ Bullish' },
  positive: { color: '#4ADE80', bg: 'rgba(34,197,94,0.08)',   border: 'rgba(34,197,94,0.2)',   label: '▲ Bullish' },
  bearish:  { color: '#FF4444', bg: 'rgba(255,51,51,0.08)',  border: 'rgba(255,51,51,0.2)',  label: '▼ Bearish' },
  BEARISH:  { color: '#FF4444', bg: 'rgba(255,51,51,0.08)',  border: 'rgba(255,51,51,0.2)',  label: '▼ Bearish' },
  NEGATIVE: { color: '#FF4444', bg: 'rgba(255,51,51,0.08)',  border: 'rgba(255,51,51,0.2)',  label: '▼ Bearish' },
  negative: { color: '#FF4444', bg: 'rgba(255,51,51,0.08)',  border: 'rgba(255,51,51,0.2)',  label: '▼ Bearish' },
  neutral:  { color: 'hsl(var(--secondary))', bg: 'rgba(146,152,166,0.08)',  border: 'rgba(146,152,166,0.2)',  label: '◆ Neutral' },
  NEUTRAL:  { color: 'hsl(var(--secondary))', bg: 'rgba(146,152,166,0.08)',  border: 'rgba(146,152,166,0.2)',  label: '◆ Neutral' },
  Neutral:  { color: 'hsl(var(--secondary))', bg: 'rgba(146,152,166,0.08)',  border: 'rgba(146,152,166,0.2)',  label: '◆ Neutral' },
};

function SentimentPill({ sentiment }) {
  if (!sentiment) return null;
  const s = SENTIMENT_STYLES[sentiment];
  if (!s) return null;
  return (
    <span
      className="text-[8px] font-mono font-bold px-1.5 py-px rounded-full border flex-shrink-0"
      style={{ color: s.color, background: s.bg, borderColor: s.border }}
    >
      {s.label}
    </span>
  );
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function NewsCard({ article, compact = false }) {
  const hasThumbnail = !!article.thumbnail_url;

  if (compact) {
    return (
      <a
        href={article.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="group flex gap-3 p-3 rounded-lg border transition-all duration-200"
        style={{ background: 'hsl(var(--muted) / 0.35)', borderColor: 'hsl(var(--muted) / 0.5)' }}
        onMouseEnter={e => {
          e.currentTarget.style.borderColor = 'hsl(var(--primary) / 0.2)';
          e.currentTarget.style.background = 'hsl(var(--primary) / 0.03)';
        }}
        onMouseLeave={e => {
          e.currentTarget.style.borderColor = 'hsl(var(--muted) / 0.5)';
          e.currentTarget.style.background = 'hsl(var(--muted) / 0.35)';
        }}
      >
        {hasThumbnail && (
          <div className="w-20 h-14 flex-shrink-0 overflow-hidden rounded-md bg-muted">
            <img
              src={article.thumbnail_url} alt=""
              className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
              onError={e => { e.target.parentElement.style.display = 'none'; }}
            />
          </div>
        )}
        <div className="flex-1 min-w-0">
          {article.tickers?.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-1.5">
              {article.tickers.slice(0, 3).map(t => (
                <span key={t} className="px-1.5 py-px text-[8px] font-mono font-bold rounded"
                  style={{ background: 'hsl(var(--primary) / 0.08)', color: '#E3B85F', border: '1px solid rgba(227,184,95,0.15)' }}>
                  {t}
                </span>
              ))}
            </div>
          )}
          <p className="text-sm text-foreground leading-snug line-clamp-2 group-hover:text-primary transition-colors duration-150">
            {article.title}
          </p>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span className="text-[10px] font-mono text-muted-foreground">{article.source}</span>
            <span className="text-muted-foreground/60 text-[10px]">·</span>
            <span className="text-[10px] font-mono text-muted-foreground/50 flex items-center gap-0.5">
              <Clock className="w-2.5 h-2.5" /> {timeAgo(article.published_at)}
            </span>
            <SentimentPill sentiment={article.sentiment} />
          </div>
        </div>
        <ExternalLink className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-50 transition-opacity flex-shrink-0 mt-0.5" />
      </a>
    );
  }

  return (
    <a
      href={article.source_url}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex flex-col rounded-lg border overflow-hidden transition-all duration-200"
      style={{ background: 'hsl(var(--muted) / 0.35)', borderColor: 'hsl(var(--muted) / 0.5)' }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'hsl(var(--primary) / 0.2)';
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = '0 8px 32px rgba(0,0,0,0.3), 0 0 0 1px rgba(227,184,95,0.08)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'hsl(var(--muted) / 0.5)';
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      {hasThumbnail && (
        <div className="w-full h-36 overflow-hidden bg-muted relative flex-shrink-0">
          <img
            src={article.thumbnail_url} alt=""
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            onError={e => { e.target.parentElement.style.display = 'none'; }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
          {article.sentiment && (
            <div className="absolute top-2 right-2"><SentimentPill sentiment={article.sentiment} /></div>
          )}
        </div>
      )}

      <div className="p-3.5 flex-1 flex flex-col gap-2">
        {article.tickers?.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {article.tickers.slice(0, 3).map(t => (
              <span key={t} className="px-1.5 py-px text-[9px] font-mono font-bold rounded"
                style={{ background: 'hsl(var(--primary) / 0.08)', color: '#E3B85F', border: '1px solid rgba(227,184,95,0.15)' }}>
                {t}
              </span>
            ))}
          </div>
        )}

        <p className="text-sm text-foreground font-medium leading-snug line-clamp-2 group-hover:text-primary transition-colors duration-150 flex-1">
          {article.title}
        </p>

        {article.summary && (
          <p className="text-xs text-muted-foreground/60 line-clamp-2 leading-relaxed">{article.summary}</p>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-border mt-auto">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-mono text-muted-foreground">{article.source}</span>
            <span className="text-muted-foreground/60">·</span>
            <span className="text-[10px] font-mono text-muted-foreground/50 flex items-center gap-0.5">
              <Clock className="w-2.5 h-2.5" /> {timeAgo(article.published_at)}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            {!hasThumbnail && <SentimentPill sentiment={article.sentiment} />}
            <ExternalLink className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-50 transition-opacity" />
          </div>
        </div>
      </div>
    </a>
  );
}
