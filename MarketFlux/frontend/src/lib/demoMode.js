import { useEffect, useState } from 'react';
import { API_BASE } from '@/lib/api';

let demoPromise = null;

export function loadDemoMode() {
  if (process.env.REACT_APP_DEMO_MODE === 'true') {
    return Promise.resolve(true);
  }
  if (!demoPromise) {
    demoPromise = fetch(`${API_BASE}/api/health`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => Boolean(data?.demo_mode))
      .catch(() => false);
  }
  return demoPromise;
}

export function useDemoMode() {
  const buildFlag = process.env.REACT_APP_DEMO_MODE === 'true';
  const [demo, setDemo] = useState(buildFlag);

  useEffect(() => {
    let cancelled = false;
    loadDemoMode().then((value) => {
      if (!cancelled) setDemo(Boolean(value));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return demo;
}
