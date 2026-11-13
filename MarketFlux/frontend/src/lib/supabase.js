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

export const supabase = supabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null;
