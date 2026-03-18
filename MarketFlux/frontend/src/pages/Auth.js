import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { LogIn, UserPlus, Activity } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

export default function Auth() {
  const { login, register, loginWithGoogle, user } = useAuth();
  const navigate = useNavigate();
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
      setError(err.response?.data?.detail || 'Login failed');
    }
    setLoading(false);
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await register(regEmail, regPassword, regName);
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen grid-bg flex items-center justify-center p-4" data-testid="auth-page">
      <Card className="rounded-none border-border dark:bg-card/50 bg-card w-full max-w-md">
        <CardHeader className="text-center pb-2">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Activity className="w-8 h-8 text-primary" />
            <span className="font-mono text-2xl font-bold text-primary glow-text-green tracking-tight">
              MARKET FLUX
            </span>
          </div>
          <CardTitle className="text-sm font-mono text-muted-foreground uppercase tracking-widest">
            Access Your Account
          </CardTitle>
        </CardHeader>
        <CardContent className="px-6 pb-6">
          {/* Google Login */}
          <Button
            data-testid="google-login-btn"
            variant="outline"
            onClick={loginWithGoogle}
            className="w-full rounded-none border-border font-mono text-xs uppercase tracking-wider mb-4 py-5 hover:bg-primary hover:text-black hover:border-primary"
          >
            <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            Continue with Google
          </Button>

          <div className="relative mb-4">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-[10px] uppercase">
              <span className="bg-card px-2 text-muted-foreground font-mono tracking-wider">or</span>
            </div>
          </div>

          {error && (
            <div className="mb-3 p-2 border border-destructive/50 bg-destructive/5 text-xs font-mono text-destructive" data-testid="auth-error">
              {error}
            </div>
          )}

          <Tabs defaultValue="login">
            <TabsList className="w-full rounded-none bg-muted border border-border">
              <TabsTrigger
                data-testid="login-tab"
                value="login"
                className="flex-1 rounded-none font-mono text-xs uppercase tracking-wider data-[state=active]:bg-primary data-[state=active]:text-black"
              >
                <LogIn className="w-3 h-3 mr-1" /> Login
              </TabsTrigger>
              <TabsTrigger
                data-testid="register-tab"
                value="register"
                className="flex-1 rounded-none font-mono text-xs uppercase tracking-wider data-[state=active]:bg-primary data-[state=active]:text-black"
              >
                <UserPlus className="w-3 h-3 mr-1" /> Register
              </TabsTrigger>
            </TabsList>

            <TabsContent value="login" className="mt-4">
              <form onSubmit={handleLogin} className="space-y-3">
                <div>
                  <Label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Email</Label>
                  <Input
                    data-testid="login-email"
                    type="email"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    required
                    className="rounded-none bg-background border-border font-mono text-sm mt-1"
                  />
                </div>
                <div>
                  <Label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Password</Label>
                  <Input
                    data-testid="login-password"
                    type="password"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    required
                    className="rounded-none bg-background border-border font-mono text-sm mt-1"
                  />
                </div>
                <Button
                  data-testid="login-submit-btn"
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-none bg-primary text-black font-mono text-xs uppercase tracking-wider hover:bg-primary/80"
                >
                  {loading ? 'Logging in...' : 'Login'}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="register" className="mt-4">
              <form onSubmit={handleRegister} className="space-y-3">
                <div>
                  <Label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Name</Label>
                  <Input
                    data-testid="register-name"
                    value={regName}
                    onChange={(e) => setRegName(e.target.value)}
                    required
                    className="rounded-none bg-background border-border font-mono text-sm mt-1"
                  />
                </div>
                <div>
                  <Label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Email</Label>
                  <Input
                    data-testid="register-email"
                    type="email"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    required
                    className="rounded-none bg-background border-border font-mono text-sm mt-1"
                  />
                </div>
                <div>
                  <Label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Password</Label>
                  <Input
                    data-testid="register-password"
                    type="password"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    required
                    className="rounded-none bg-background border-border font-mono text-sm mt-1"
                  />
                </div>
                <Button
                  data-testid="register-submit-btn"
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-none bg-primary text-black font-mono text-xs uppercase tracking-wider hover:bg-primary/80"
                >
                  {loading ? 'Creating account...' : 'Create Account'}
                </Button>
              </form>
            </TabsContent>
          </Tabs>

          <p className="text-[10px] text-muted-foreground/50 text-center mt-4 font-mono">
            This platform does not provide financial advice.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
