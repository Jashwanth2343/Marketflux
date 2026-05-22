import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.REACT_APP_SUPABASE_URL;
const supabaseAnonKey = process.env.REACT_APP_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    'Supabase is not configured. Create frontend/.env.local from .env.example and set ' +
    'REACT_APP_SUPABASE_URL and REACT_APP_SUPABASE_ANON_KEY, then restart the dev server.'
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
