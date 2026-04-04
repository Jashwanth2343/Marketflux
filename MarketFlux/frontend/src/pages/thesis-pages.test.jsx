import React, { act } from 'react';
import { createRoot } from 'react-dom/client';

import Theses from '@/pages/Theses';
import ThesisWorkspace from '@/pages/ThesisWorkspace';
import thesisApi from '../lib/thesisApi';
import { useAuth } from '../contexts/AuthContext';

jest.mock('react-router-dom', () => {
  const ReactLib = require('react');
  return {
    Link: ({ to, children, ...props }) => ReactLib.createElement('a', { href: to, ...props }, children),
    useNavigate: () => jest.fn(),
    useParams: () => ({ thesisId: 'thesis-1' }),
  };
}, { virtual: true });

jest.mock('../lib/thesisApi', () => ({
  __esModule: true,
  default: {
    listTheses: jest.fn(),
    getThesis: jest.fn(),
    reviseThesis: jest.fn(),
    createMemo: jest.fn(),
  },
}));

jest.mock('../contexts/AuthContext', () => ({
  useAuth: jest.fn(),
}));

if (!global.TextEncoder) {
  const { TextEncoder } = require('util');
  global.TextEncoder = TextEncoder;
}

const mockedUseAuth = useAuth;
const mockedThesisApi = thesisApi;

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function renderElement(element) {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);

  await act(async () => {
    root.render(element);
  });

  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

  return {
    container,
    unmount: async () => {
      await act(async () => {
        root.unmount();
      });
      container.remove();
    },
  };
}

afterEach(() => {
  jest.clearAllMocks();
  document.body.innerHTML = '';
});

test('theses page prompts for login when the user is not authenticated', async () => {
  mockedUseAuth.mockReturnValue({ user: null, loading: false });

  const view = await renderElement(<Theses />);

  expect(view.container.textContent).toContain('Login required');
  expect(view.container.textContent).toContain('private to your account');

  await view.unmount();
});

test('thesis workspace renders fetched thesis details for an authenticated user', async () => {
  mockedUseAuth.mockReturnValue({ user: { id: 'user-123' }, loading: false });
  mockedThesisApi.getThesis.mockResolvedValue({
    item: {
      thesis: {
        id: 'thesis-1',
        ticker: 'NVDA',
        claim: 'AI infrastructure demand remains supply constrained.',
        why_now: 'Hyperscaler capex is still accelerating.',
        time_horizon: 'medium_term',
        status: 'active',
        invalidation_conditions: ['Orders slow materially'],
        updated_at: '2026-04-03T10:00:00Z',
      },
      latest_revision: {
        id: 'revision-1',
        version: 1,
        status: 'active',
      },
      revisions: [
        {
          id: 'revision-1',
          version: 1,
          status: 'active',
          claim: 'AI infrastructure demand remains supply constrained.',
          why_now: 'Hyperscaler capex is still accelerating.',
          time_horizon: 'medium_term',
          created_at: '2026-04-03T10:00:00Z',
        },
      ],
      evidence_blocks: [
        {
          id: 'evidence-1',
          source: 'news',
          summary: 'Major cloud vendors signaled higher AI infrastructure demand.',
          confidence: 76,
          freshness: 4,
          links: [{ label: 'Source', value: 'https://example.com' }],
          observed_at: '2026-04-03T09:30:00Z',
        },
      ],
      evidence_groups: {
        news: [
          {
            id: 'evidence-1',
            source: 'news',
            summary: 'Major cloud vendors signaled higher AI infrastructure demand.',
            confidence: 76,
            freshness: 4,
            links: [{ label: 'Source', value: 'https://example.com' }],
            observed_at: '2026-04-03T09:30:00Z',
          },
        ],
      },
      memos: [],
      paper_trades: [],
    },
  });

  const view = await renderElement(<ThesisWorkspace />);

  expect(view.container.textContent).toContain('NVDA');
  expect(view.container.textContent).toContain('AI infrastructure demand remains supply constrained.');
  expect(view.container.textContent).toContain('Major cloud vendors signaled higher AI infrastructure demand.');

  await view.unmount();
});
