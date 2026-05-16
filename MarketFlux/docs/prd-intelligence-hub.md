# PRD: Intelligence Hub

## Problem Statement
Research, news, screener, macro, and thesis features are scattered across 5+ separate nav items. Users can't find related information without navigating between pages. The nav has 11 items which is overwhelming.

## Scope

### In Scope
- Consolidate News, AI Screener, Research Center, Macro Dashboard, and Theses into one page
- Sub-tab navigation synced to URL params (`?tab=research`)
- Each existing page gets `embedded` prop to render without its own wrapper
- Thesis detail/workspace remains a dedicated route under `/intelligence/thesis/:id`
- Legacy URL redirects for bookmarks

### Out of Scope
- Rewriting any existing page content
- New research/thesis features
- Cross-tab data sharing (each tab fetches independently)

## Component Structure

```
Intelligence.js (shell)
  ├── Tabs (synced to ?tab= URL param)
  │   ├── Research → <ResearchCenter embedded />
  │   ├── News → <NewsFeed embedded />
  │   ├── Screener → <AIScreener embedded />
  │   ├── Macro → <MacroDashboard embedded />
  │   └── Theses → <Theses embedded />
  └── Sub-routes:
      ├── /intelligence/thesis/new → <ThesisNew />
      ├── /intelligence/thesis/:id → <ThesisWorkspace />
      └── /intelligence/thesis/:id/trade-lab → <ThesisTradeLab />
```

## Files to Create/Modify

| File | Action |
|------|--------|
| `pages/Intelligence.js` | Create (~130 lines) |
| `pages/NewsFeed.js` | Modify (add embedded prop) |
| `pages/AIScreener.js` | Modify (add embedded prop) |
| `pages/ResearchCenter.js` | Modify (add embedded prop) |
| `pages/MacroDashboard.js` | Modify (add embedded prop) |
| `pages/Theses.js` | Modify (add embedded prop + update links) |
| `pages/ThesisWorkspace.js` | Modify (update links) |
| `pages/ThesisTradeLab.js` | Modify (update links) |

## Embedded Page Pattern
```jsx
export default function PageName({ embedded = false }) {
  const content = (<>{/* page body */}</>);
  if (embedded) return content;
  return <div className="p-4 lg:p-6 min-h-screen">{content}</div>;
}
```

## Acceptance Criteria
- [ ] `/intelligence` loads with Research tab active by default
- [ ] All 5 tabs render their content correctly
- [ ] `?tab=news` opens directly to News tab
- [ ] Thesis links navigate to `/intelligence/thesis/:id`
- [ ] Legacy redirects work: `/news` → `/intelligence?tab=news`, etc.
- [ ] No duplicate data fetching (tabs only fetch when activated)
