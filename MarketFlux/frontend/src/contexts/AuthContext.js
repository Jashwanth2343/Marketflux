import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { supabase } from '@/lib/supabase';
import api from '@/lib/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      setSession(s);
      if (s?.user) {
        setUser(_mapSupabaseUser(s.user));
      }
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
      setUser(s?.user ? _mapSupabaseUser(s.user) : null);
    });

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!session?.access_token) return;
    api.defaults.headers.common['Authorization'] = `Bearer ${session.access_token}`;
  }, [session]);

  const login = async (email, password) => {
    let result;
    try {
      result = await supabase.auth.signInWithPassword({ email, password });
    } catch {
      throw new Error('Unable to connect to auth service. Please try again.');
    }
    if (result.error) throw new Error(result.error.message);
    setUser(_mapSupabaseUser(result.data.user));
    return result.data;
  };

  const register = async (email, password, name) => {
    let result;
    try {
      result = await supabase.auth.signUp({
        email,
        password,
        options: { data: { full_name: name } },
      });
    } catch {
      throw new Error('Unable to connect to auth service. Please try again.');
    }
    if (result.error) throw new Error(result.error.message);
    if (result.data.user) setUser(_mapSupabaseUser(result.data.user));
    return result.data;
  };

  const logout = async () => {
    await supabase.auth.signOut();
    delete api.defaults.headers.common['Authorization'];
    setUser(null);
    setSession(null);
  };

  const loginWithGoogle = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin + '/' },
    });
    if (error) throw error;
  };

  const checkAuth = useCallback(async () => {
    const { data: { session: s } } = await supabase.auth.getSession();
    if (s?.user) {
      setSession(s);
      setUser(_mapSupabaseUser(s.user));
    } else {
      setUser(null);
      setSession(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, session, setUser, loading, login, register, logout, loginWithGoogle, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

function _mapSupabaseUser(u) {
  return {
    user_id: u.id,
    email: u.email,
    name: u.user_metadata?.full_name || u.email?.split('@')[0] || '',
    avatar_url: u.user_metadata?.avatar_url || null,
    provider: u.app_metadata?.provider || 'email',
  };
}
