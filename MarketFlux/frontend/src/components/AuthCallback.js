import { useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { supabase } from '@/lib/supabase';

export default function AuthCallback() {
  const hasProcessed = useRef(false);
  const navigate = useNavigate();
  const { checkAuth } = useAuth();

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    // Supabase OAuth returns tokens in the URL hash/query after redirect.
    // The supabase-js client auto-detects and stores the session.
    if (!supabase) { navigate('/auth', { replace: true }); return; }
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        checkAuth().then(() => navigate('/', { replace: true }));
      } else {
        navigate('/auth', { replace: true });
      }
    });
  }, [navigate, checkAuth]);

  return (
    <div className="flex items-center justify-center h-screen bg-background">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent animate-spin mx-auto mb-4" />
        <p className="font-mono text-primary glow-text-green text-sm uppercase tracking-widest">
          Authenticating...
        </p>
      </div>
    </div>
  );
}
