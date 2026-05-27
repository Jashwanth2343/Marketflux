import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.REACT_APP_SUPABASE_URL;
const supabaseAnonKey = process.env.REACT_APP_SUPABASE_ANON_KEY;

const supabaseConfigured = supabaseUrl && supabaseAnonKey &&
  !supabaseUrl.includes('your-project') && !supabaseAnonKey.includes('your-anon-key');

if (!supabaseConfigured) {
  console.warn(
    '[MarketFlux] Supabase not configured — auth disabled. Set ' +
    'REACT_APP_SUPABASE_URL and REACT_APP_SUPABASE_ANON_KEY in frontend/.env.local to enable.'
  );
}

// The Emergent platform injects emergent-main.js, which wraps window.fetch and
// calls response.text() on every NON-OK response (to report it to the parent
// frame). That drains the body before supabase-js can read it, surfacing as
// "Failed to execute 'json' on 'Response': body stream already read" — and it
// masks the real auth error (e.g. a 500 from signup). emergent-main.js only
// patches the TOP window, so a same-origin iframe exposes a pristine native
// fetch it never touched. We route all supabase auth traffic through that.
let _nativeFetch = null;
function getNativeFetch() {
  if (_nativeFetch) return _nativeFetch;
  try {
    const frame = document.createElement('iframe');
    frame.style.display = 'none';
    document.body.appendChild(frame);
    // Keep the frame attached — its contentWindow.fetch must stay live.
    _nativeFetch = frame.contentWindow.fetch.bind(frame.contentWindow);
  } catch {
    _nativeFetch = window.fetch.bind(window);
  }
  return _nativeFetch;
}

// Belt-and-suspenders: also buffer the body from a clone so any repeated read
// inside supabase-js serves the cached copy instead of a consumed stream.
const safeFetch = async (input, init) => {
  const response = await getNativeFetch()(input, init);
  try {
    const buffered = await response.clone().text();
    response.json = () => Promise.resolve(JSON.parse(buffered));
    response.text = () => Promise.resolve(buffered);
  } catch {
    // Body not clonable here — return the original response unchanged.
  }
  return response;
};

export const supabase = supabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey, { global: { fetch: safeFetch } })
  : null;
