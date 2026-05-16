import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { LogIn, UserPlus, Activity, Eye, EyeOff, AlertCircle, CheckCircle2, ShieldCheck, Zap, BarChart2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

function PasswordStrength({ password }) {
  if (!password) return null;
  const checks = [
    { label: '8+ chars', ok: password.length >= 8 },
    { label: 'Uppercase', ok: /[A-Z]/.test(password) },
    { label: 'Number', ok: /\d/.test(password) },
    { label: 'Symbol', ok: /[^A-Za-z0-9]/.test(password) },
  ];
  const score = checks.filter(c => c.ok).length;
  const colors = ['#FF3333', '#FF3333', '#FFB000', '#00FF41', '#00FF41'];
  const labels = ['', 'Weak', 'Weak', 'Good', 'Strong'];
  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex gap-1">
        {[0, 1, 2, 3].map(i => (
          <div
            key={i}
            className="h-1 flex-1 rounded-full transition-all duration-300"
            style={{ background: i < score ? colors[score] : 'rgba(255,255,255,0.08)' }}
          />
        ))}
      </div>
      <div className="flex items-center justify-between">
        <div className="flex gap-2 flex-wrap">
          {checks.map(({ label, ok }) => (
            <span
              key={label}
              className="text-[9px] font-mono flex items-center gap-0.5 transition-colors"
              style={{ color: ok ? '#00FF41' : 'rgba(255,255,255,0.3)' }}
            >
              <span style={{ fontSize: '8px' }}>{ok ? '✓' : '○'}</span> {label}
            </span>
          ))}
        </div>
        {score > 0 && (
          <span className="text-[9px] font-mono font-bold" style={{ color: colors[score] }}>
            {labels[score]}
          </span>
        )}
      </div>
    </div>
  );
}

export default function Auth() {
  const { login, register, loginWithGoogle, user } = useAuth();
  const navigate = useNavigate();
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [showLoginPw, setShowLoginPw] = useState(false);
  const [showRegPw, setShowRegPw] = useState(false);

  if (user) {
    navigate('/');
    return null;
  }

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(loginEmail, loginPassword);
      navigate('/');
    } catch (err) {
      setError(err.message || err.response?.data?.detail || 'Invalid credentials. Please try again.');
    }
    setLoading(false);
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await register(regEmail, regPassword, regName);
      setSuccess('Account created! Redirecting...');
      setTimeout(() => navigate('/'), 800);
    } catch (err) {
      setError(err.message || err.response?.data?.detail || 'Registration failed. Please try again.');
    }
    setLoading(false);
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
      data-testid="auth-page"
      style={{
        background: 'radial-gradient(ellipse at 20% 50%, rgba(0,255,65,0.06) 0%, transparent 50%), radial-gradient(ellipse at 80% 20%, rgba(0,243,255,0.05) 0%, transparent 40%), #09100d'
      }}
    >
      {/* Animated grid lines */}
      <div className="absolute inset-0 pointer-events-none" style={{
        backgroundImage: 'linear-gradient(rgba(0,255,65,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,65,0.03) 1px, transparent 1px)',
        backgroundSize: '60px 60px'
      }} />

      {/* Floating stat pills — trust signals */}
      <div className="absolute top-8 left-8 hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-full border border-[rgba(0,255,65,0.15)] bg-[rgba(0,255,65,0.04)]">
        <BarChart2 className="w-3 h-3 text-[#00FF41]" />
        <span className="text-[10px] font-mono text-[#00FF41]">Live Market Data</span>
      </div>
      <div className="absolute top-8 right-8 hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-full border border-[rgba(0,243,255,0.15)] bg-[rgba(0,243,255,0.04)]">
        <ShieldCheck className="w-3 h-3 text-[#00F3FF]" />
        <span className="text-[10px] font-mono text-[#00F3FF]">Secure &amp; Encrypted</span>
      </div>
      <div className="absolute bottom-8 left-8 hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-full border border-[rgba(255,176,0,0.15)] bg-[rgba(255,176,0,0.04)]">
        <Zap className="w-3 h-3 text-[#FFB000]" />
        <span className="text-[10px] font-mono text-[#FFB000]">AI-Powered Research</span>
      </div>

      <Card
        className="w-full max-w-md relative z-10 border-[rgba(0,255,65,0.15)] shadow-2xl"
        style={{
          background: 'linear-gradient(160deg, rgba(12,20,14,0.97) 0%, rgba(8,14,10,0.99) 100%)',
          backdropFilter: 'blur(24px)',
          boxShadow: '0 0 0 1px rgba(0,255,65,0.08), 0 32px 80px rgba(0,0,0,0.6), 0 0 80px rgba(0,255,65,0.03)'
        }}
      >
        {/* Top accent line */}
        <div className="absolute top-0 left-8 right-8 h-px" style={{ background: 'linear-gradient(90deg, transparent, rgba(0,255,65,0.4), transparent)' }} />

        <CardHeader className="text-center pb-3 pt-8">
          <div className="flex items-center justify-center gap-2.5 mb-5">
            <div className="relative">
              <Activity className="w-8 h-8 text-[#00FF41]" style={{ filter: 'drop-shadow(0 0 8px rgba(0,255,65,0.6))' }} />
            </div>
            <span className="font-mono text-2xl font-bold text-[#00FF41] tracking-tight" style={{ textShadow: '0 0 20px rgba(0,255,65,0.4)' }}>
              MARKET FLUX
            </span>
          </div>
          <p className="text-[10px] font-mono text-[rgba(255,255,255,0.35)] uppercase tracking-[0.3em]">
            AI-Native Quant Research Terminal
          </p>
        </CardHeader>

        <CardContent className="px-6 pb-8">
          {/* Google Login */}
          <Button
            data-testid="google-login-btn"
            variant="outline"
            onClick={loginWithGoogle}
            className="w-full font-mono text-xs uppercase tracking-wider mb-5 py-5 transition-all duration-200 group"
            style={{
              borderColor: 'rgba(255,255,255,0.12)',
              background: 'rgba(255,255,255,0.03)',
              color: 'rgba(255,255,255,0.8)'
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(0,255,65,0.3)'; e.currentTarget.style.background = 'rgba(0,255,65,0.05)'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)'; e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
          >
            <svg className="w-4 h-4 mr-2.5" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Continue with Google
          </Button>

          <div className="relative mb-5">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-[rgba(255,255,255,0.07)]" />
            </div>
            <div className="relative flex justify-center">
              <span className="px-3 text-[10px] uppercase font-mono tracking-widest text-[rgba(255,255,255,0.25)]"
                style={{ background: 'rgba(10,17,12,0.98)' }}>
                or
              </span>
            </div>
          </div>

          {/* Error / Success banners */}
          {error && (
            <div
              className="mb-4 p-3 flex items-start gap-2.5 text-xs font-mono border rounded"
              style={{ borderColor: 'rgba(255,51,51,0.3)', background: 'rgba(255,51,51,0.06)', color: '#FF5555' }}
              data-testid="auth-error"
            >
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              {error}
            </div>
          )}
          {success && (
            <div
              className="mb-4 p-3 flex items-start gap-2.5 text-xs font-mono border rounded"
              style={{ borderColor: 'rgba(0,255,65,0.3)', background: 'rgba(0,255,65,0.06)', color: '#00FF41' }}
            >
              <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              {success}
            </div>
          )}

          <Tabs defaultValue="login">
            <TabsList
              className="w-full mb-5 p-0.5 gap-0.5"
              style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}
            >
              <TabsTrigger
                data-testid="login-tab"
                value="login"
                className="flex-1 font-mono text-xs uppercase tracking-wider py-2 transition-all duration-200 data-[state=active]:text-black"
                style={{'--tab-active-bg': '#00FF41'}}
              >
                <LogIn className="w-3 h-3 mr-1.5" /> Login
              </TabsTrigger>
              <TabsTrigger
                data-testid="register-tab"
                value="register"
                className="flex-1 font-mono text-xs uppercase tracking-wider py-2 transition-all duration-200 data-[state=active]:text-black"
              >
                <UserPlus className="w-3 h-3 mr-1.5" /> Register
              </TabsTrigger>
            </TabsList>

            {/* LOGIN */}
            <TabsContent value="login" className="mt-0 space-y-4">
              <form onSubmit={handleLogin} className="space-y-4">
                <div className="space-y-1.5">
                  <Label className="text-[10px] font-mono uppercase tracking-widest text-[rgba(255,255,255,0.4)]">
                    Email
                  </Label>
                  <Input
                    data-testid="login-email"
                    type="email"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    required
                    autoComplete="email"
                    placeholder="you@example.com"
                    className="font-mono text-sm transition-all duration-200"
                    style={{
                      background: 'rgba(255,255,255,0.03)',
                      borderColor: loginEmail ? 'rgba(0,255,65,0.25)' : 'rgba(255,255,255,0.1)',
                    }}
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label className="text-[10px] font-mono uppercase tracking-widest text-[rgba(255,255,255,0.4)]">
                      Password
                    </Label>
                    <button
                      type="button"
                      className="text-[10px] font-mono text-[rgba(0,243,255,0.5)] hover:text-[#00F3FF] transition-colors"
                      onClick={() => {}}
                      tabIndex={-1}
                    >
                      Forgot password?
                    </button>
                  </div>
                  <div className="relative">
                    <Input
                      data-testid="login-password"
                      type={showLoginPw ? 'text' : 'password'}
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                      required
                      autoComplete="current-password"
                      placeholder="••••••••"
                      className="font-mono text-sm pr-10 transition-all duration-200"
                      style={{
                        background: 'rgba(255,255,255,0.03)',
                        borderColor: loginPassword ? 'rgba(0,255,65,0.25)' : 'rgba(255,255,255,0.1)',
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowLoginPw(v => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[rgba(255,255,255,0.3)] hover:text-[rgba(255,255,255,0.7)] transition-colors"
                      tabIndex={-1}
                    >
                      {showLoginPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <Button
                  data-testid="login-submit-btn"
                  type="submit"
                  disabled={loading}
                  className="w-full font-mono text-xs uppercase tracking-wider py-5 transition-all duration-200 mt-2"
                  style={{
                    background: loading ? 'rgba(0,255,65,0.4)' : '#00FF41',
                    color: '#000',
                    boxShadow: loading ? 'none' : '0 0 20px rgba(0,255,65,0.25)'
                  }}
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <span className="w-3 h-3 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                      Authenticating...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <LogIn className="w-3 h-3" /> Login
                    </span>
                  )}
                </Button>
              </form>
            </TabsContent>

            {/* REGISTER */}
            <TabsContent value="register" className="mt-0 space-y-4">
              <form onSubmit={handleRegister} className="space-y-4">
                <div className="space-y-1.5">
                  <Label className="text-[10px] font-mono uppercase tracking-widest text-[rgba(255,255,255,0.4)]">
                    Full Name
                  </Label>
                  <Input
                    data-testid="register-name"
                    value={regName}
                    onChange={(e) => setRegName(e.target.value)}
                    required
                    placeholder="Jane Smith"
                    className="font-mono text-sm transition-all duration-200"
                    style={{
                      background: 'rgba(255,255,255,0.03)',
                      borderColor: regName ? 'rgba(0,255,65,0.25)' : 'rgba(255,255,255,0.1)',
                    }}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-[10px] font-mono uppercase tracking-widest text-[rgba(255,255,255,0.4)]">
                    Email
                  </Label>
                  <Input
                    data-testid="register-email"
                    type="email"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    required
                    placeholder="you@example.com"
                    className="font-mono text-sm transition-all duration-200"
                    style={{
                      background: 'rgba(255,255,255,0.03)',
                      borderColor: regEmail ? 'rgba(0,255,65,0.25)' : 'rgba(255,255,255,0.1)',
                    }}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-[10px] font-mono uppercase tracking-widest text-[rgba(255,255,255,0.4)]">
                    Password
                  </Label>
                  <div className="relative">
                    <Input
                      data-testid="register-password"
                      type={showRegPw ? 'text' : 'password'}
                      value={regPassword}
                      onChange={(e) => setRegPassword(e.target.value)}
                      required
                      placeholder="Min. 8 characters"
                      className="font-mono text-sm pr-10 transition-all duration-200"
                      style={{
                        background: 'rgba(255,255,255,0.03)',
                        borderColor: regPassword ? 'rgba(0,255,65,0.25)' : 'rgba(255,255,255,0.1)',
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowRegPw(v => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[rgba(255,255,255,0.3)] hover:text-[rgba(255,255,255,0.7)] transition-colors"
                      tabIndex={-1}
                    >
                      {showRegPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <PasswordStrength password={regPassword} />
                </div>

                <Button
                  data-testid="register-submit-btn"
                  type="submit"
                  disabled={loading}
                  className="w-full font-mono text-xs uppercase tracking-wider py-5 transition-all duration-200 mt-2"
                  style={{
                    background: loading ? 'rgba(0,255,65,0.4)' : '#00FF41',
                    color: '#000',
                    boxShadow: loading ? 'none' : '0 0 20px rgba(0,255,65,0.25)'
                  }}
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <span className="w-3 h-3 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                      Creating account...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <UserPlus className="w-3 h-3" /> Create Account
                    </span>
                  )}
                </Button>
              </form>
            </TabsContent>
          </Tabs>

          <p className="text-[9px] text-center mt-5 font-mono leading-relaxed" style={{ color: 'rgba(255,255,255,0.2)' }}>
            For research purposes only. Not financial advice.<br />
            By continuing you agree to our Terms of Service.
          </p>
        </CardContent>

        {/* Bottom accent line */}
        <div className="absolute bottom-0 left-8 right-8 h-px" style={{ background: 'linear-gradient(90deg, transparent, rgba(0,243,255,0.2), transparent)' }} />
      </Card>
    </div>
  );
}
