import { useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/lib/api';

export default function AuthCallback() {
  const hasProcessed = useRef(false);
  const navigate = useNavigate();
  const { setUser } = useAuth();

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash;
    const params = new URLSearchParams(hash.substring(1));
    const sessionId = params.get('session_id');

    if (sessionId) {
      api.post('/auth/google-session', { session_id: sessionId })
        .then(res => {
          localStorage.setItem('mf_token', res.data.token);
          setUser(res.data.user);
          navigate('/', { replace: true, state: { user: res.data.user } });
        })
        .catch(() => {
          navigate('/auth', { replace: true });
        });
    } else {
      navigate('/', { replace: true });
    }
  }, [navigate, setUser]);

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
