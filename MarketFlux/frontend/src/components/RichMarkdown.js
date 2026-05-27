import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Premium markdown renderer for agent output — styled tables, headings, lists,
 * code and callouts so responses read like a research note, not plain text.
 */
const components = {
    h1: ({ node, ...p }) => <h1 className="mt-4 mb-2 text-lg font-semibold tracking-tight text-foreground" {...p} />,
    h2: ({ node, ...p }) => (
        <h2 className="mt-4 mb-2 flex items-center gap-2 text-base font-semibold tracking-tight text-foreground border-b border-white/10 pb-1" {...p} />
    ),
    h3: ({ node, ...p }) => <h3 className="mt-3 mb-1.5 text-sm font-semibold uppercase tracking-wider text-primary" {...p} />,
    p: ({ node, ...p }) => <p className="my-2 leading-relaxed text-foreground/90" {...p} />,
    strong: ({ node, ...p }) => <strong className="font-semibold text-foreground" {...p} />,
    em: ({ node, ...p }) => <em className="text-foreground/80" {...p} />,
    a: ({ node, ...p }) => <a className="text-primary underline-offset-2 hover:underline" target="_blank" rel="noreferrer" {...p} />,
    ul: ({ node, ...p }) => <ul className="my-2 space-y-1 pl-1" {...p} />,
    ol: ({ node, ...p }) => <ol className="my-2 list-decimal space-y-1 pl-5 marker:text-muted-foreground" {...p} />,
    li: ({ node, children, ...p }) => (
        <li className="flex gap-2 text-foreground/90 [li>&]:list-item" {...p}>
            <span className="mt-2 h-1 w-1 flex-shrink-0 rounded-full bg-primary/60" />
            <span className="min-w-0 flex-1">{children}</span>
        </li>
    ),
    blockquote: ({ node, ...p }) => (
        <blockquote className="my-2 border-l-2 border-primary/40 bg-white/[0.02] py-1 pl-3 text-muted-foreground" {...p} />
    ),
    hr: () => <hr className="my-3 border-white/10" />,
    code: ({ node, inline, className, children, ...p }) =>
        inline ? (
            <code className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[0.85em] text-emerald-300" {...p}>{children}</code>
        ) : (
            <code className="block overflow-x-auto rounded-lg border border-white/10 bg-black/50 p-3 font-mono text-xs leading-relaxed text-emerald-300/90" {...p}>{children}</code>
        ),
    pre: ({ node, children }) => <pre className="my-2">{children}</pre>,
    table: ({ node, ...p }) => (
        <div className="my-3 overflow-x-auto rounded-xl border border-white/10">
            <table className="w-full border-collapse text-sm" {...p} />
        </div>
    ),
    thead: ({ node, ...p }) => <thead className="bg-white/[0.04]" {...p} />,
    th: ({ node, ...p }) => (
        <th className="border-b border-white/10 px-3 py-2 text-left text-[11px] font-mono font-semibold uppercase tracking-wider text-primary" {...p} />
    ),
    td: ({ node, ...p }) => <td className="border-b border-white/5 px-3 py-2 text-foreground/90 tabular-nums" {...p} />,
    tr: ({ node, ...p }) => <tr className="transition-colors hover:bg-white/[0.02]" {...p} />,
};

export default function RichMarkdown({ children }) {
    return (
        <div className="text-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {children || ''}
            </ReactMarkdown>
        </div>
    );
}
