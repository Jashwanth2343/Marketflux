import { Brain, Newspaper, Filter, Globe, BookOpenText } from 'lucide-react';

/* Single source of truth for the Intelligence terminal's functions. Each has a
   Bloomberg-style code, the tab it maps to, a numeric hotkey, and command aliases. */
export const FUNCTIONS = [
  { code: 'RES', tab: 'research', n: 1, label: 'Research', desc: 'AI ideas, signals & memos', icon: Brain, aliases: ['res', 'research', 'idea', 'ideas'] },
  { code: 'N', tab: 'news', n: 2, label: 'News', desc: 'Live sentiment-tagged headlines', icon: Newspaper, aliases: ['n', 'news', 'headlines'] },
  { code: 'SCR', tab: 'screener', n: 3, label: 'Screener', desc: 'Natural-language equity screen', icon: Filter, aliases: ['scr', 'screen', 'screener'] },
  { code: 'MAC', tab: 'macro', n: 4, label: 'Macro', desc: 'Regime, rates, cross-asset', icon: Globe, aliases: ['mac', 'macro', 'regime'] },
  { code: 'TH', tab: 'theses', n: 5, label: 'Theses', desc: 'Living investment theses', icon: BookOpenText, aliases: ['th', 'thesis', 'theses'] },
];

export const TAB_VALUES = FUNCTIONS.map((f) => f.tab);

export function findFunction(token) {
  const q = String(token).toLowerCase();
  return FUNCTIONS.find((f) => f.code.toLowerCase() === q || f.aliases.includes(q));
}

export function functionByTab(tab) {
  return FUNCTIONS.find((f) => f.tab === tab);
}
