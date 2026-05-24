import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.REACT_APP_SUPABASE_URL;
const supabaseAnonKey = process.env.REACT_APP_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    'Supabase is not configured. Copy frontend/.env.example to frontend/.env.local and set ' +
    'REACT_APP_SUPABASE_URL and REACT_APP_SUPABASE_ANON_KEY, then restart the dev server. ' +
    'For production builds these REACT_APP_* vars must be set in the build environment.'
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
