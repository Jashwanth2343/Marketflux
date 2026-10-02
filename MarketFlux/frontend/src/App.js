import React, { useState, useEffect, lazy, Suspense } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation, useParams } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import TopNav from "@/components/TopNav";

const AIChatbot = lazy(() => import("@/components/AIChatbot"));
import ScanlineOverlay from "@/components/ScanlineOverlay";
import AuthCallback from "@/components/AuthCallback";
// Route-level code splitting: heavy pages load on demand, keeping the
// initial bundle lean. Each is rendered inside the Suspense below.
const Dashboard = lazy(() => import("@/pages/Dashboard"));
const Intelligence = lazy(() => import("@/pages/Intelligence"));
const Copilot = lazy(() => import("@/pages/Copilot"));
const PortfolioRisk = lazy(() => import("@/pages/PortfolioRisk"));
const Backtest = lazy(() => import("@/pages/Backtest"));
const StockDetail = lazy(() => import("@/pages/StockDetail"));
const ThesisNew = lazy(() => import("@/pages/ThesisNew"));
const ThesisWorkspace = lazy(() => import("@/pages/ThesisWorkspace"));
const ThesisTradeLab = lazy(() => import("@/pages/ThesisTradeLab"));
const Auth = lazy(() => import("@/pages/Auth"));
const PilotLeaderboard = lazy(() => import("@/pages/PilotLeaderboard"));
const PilotPublicProfile = lazy(() => import("@/pages/PilotPublicProfile"));
const Ledger = lazy(() => import("@/pages/Ledger"));
import { Toaster } from "@/components/ui/sonner";
import { Sparkles } from "lucide-react";

function RouteFallback() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/10 border-b-primary" />
    </div>
  );
}

function ThesisRedirect() {
  const { thesisId } = useParams();
  return <Navigate to={`/intelligence/thesis/${thesisId}`} replace />;
}

function ThesisTradLabRedirect() {
  const { thesisId } = useParams();
  return <Navigate to={`/intelligence/thesis/${thesisId}/trade-lab`} replace />;
}

function PilotProfileRedirect() {
  const { slug } = useParams();
  return <Navigate to={`/leaderboard/p/${slug}`} replace />;
}

function FundOSTerminalRedirect() {
  const { strategyId } = useParams();
  return <Navigate to={`/copilot?tab=studio&strategy=${strategyId}`} replace />;
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(error, info) {
    console.error('App error:', error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background flex items-center justify-center">
          <div className="text-center p-8">
            <h1 className="text-2xl font-bold text-white mb-4">Something went wrong</h1>
            <p className="text-gray-400 mb-6">The application encountered an unexpected error.</p>
            <button onClick={() => { this.setState({ hasError: false }); window.location.href = '/'; }} className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-500">
              Return to Dashboard
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

class ChatErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch() {
    this.props.onError?.();
  }
  render() {
    if (this.state.hasError) {
      return (
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="fixed bottom-6 right-6 z-[999] flex items-center gap-2 px-5 py-3.5 rounded-full shadow-lg font-semibold text-sm"
          style={{ background: 'var(--mf-accent)', color: 'var(--mf-accent-fg)' }}
          title="Flux AI failed to load — click to reload"
        >
          <Sparkles className="w-5 h-5" />
          <span className="hidden sm:inline">Reload Flux AI</span>
        </button>
      );
    }
    return this.props.children;
  }
}

function AppRouter() {
  const location = useLocation();
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatWidth, setChatWidth] = useState(380);
  const [isDesktop, setIsDesktop] = useState(window.innerWidth >= 1024);
  const [chatFailed, setChatFailed] = useState(false);

  const openFluxChat = () => {
    setChatFailed(false);
    window.dispatchEvent(new Event("marketflux:open-terminal"));
  };

  useEffect(() => {
    const handleResize = () => setIsDesktop(window.innerWidth >= 1024);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    const openTerminal = () => setIsChatOpen(true);
    const closeTerminal = () => setIsChatOpen(false);
    window.addEventListener("marketflux:open-terminal", openTerminal);
    window.addEventListener("marketflux:close-terminal", closeTerminal);
    return () => {
      window.removeEventListener("marketflux:open-terminal", openTerminal);
      window.removeEventListener("marketflux:close-terminal", closeTerminal);
    };
  }, []);

  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  const mainMarginRight = isDesktop && isChatOpen ? chatWidth : 0;

  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-background overflow-hidden relative">
        <div
          className="flex-1 flex flex-col h-full overflow-hidden transition-all duration-300 ease-in-out"
          style={{ marginRight: mainMarginRight }}
        >
          <TopNav />
          <main className="flex-1 overflow-y-auto flex flex-col relative w-full">
            <Suspense fallback={<RouteFallback />}>
            <Routes>
              {/* Core pages */}
              <Route path="/" element={<Dashboard />} />
              <Route path="/intelligence" element={<Intelligence />} />
              <Route path="/intelligence/thesis/new" element={<ThesisNew />} />
              <Route path="/intelligence/thesis/:thesisId" element={<ThesisWorkspace />} />
              <Route path="/intelligence/thesis/:thesisId/trade-lab" element={<ThesisTradeLab />} />
              <Route path="/copilot" element={<Copilot />} />
              <Route path="/ledger" element={<Ledger />} />
              <Route path="/backtest" element={<Backtest />} />
              <Route path="/portfolio" element={<PortfolioRisk />} />
              <Route path="/leaderboard" element={<PilotLeaderboard />} />
              <Route path="/leaderboard/p/:slug" element={<PilotPublicProfile />} />
              <Route path="/stock/:ticker" element={<StockDetail />} />
              <Route path="/auth" element={<Auth />} />

              {/* Legacy redirects */}
              <Route path="/news" element={<Navigate to="/intelligence?tab=news" replace />} />
              <Route path="/screener" element={<Navigate to="/intelligence?tab=screener" replace />} />
              <Route path="/research" element={<Navigate to="/intelligence?tab=research" replace />} />
              <Route path="/macro" element={<Navigate to="/intelligence?tab=macro" replace />} />
              <Route path="/theses" element={<Navigate to="/intelligence?tab=theses" replace />} />
              <Route path="/theses/new" element={<Navigate to="/intelligence/thesis/new" replace />} />
              <Route path="/theses/:thesisId" element={<ThesisRedirect />} />
              <Route path="/theses/:thesisId/trade-lab" element={<ThesisTradLabRedirect />} />
              <Route path="/risk" element={<Navigate to="/portfolio?tab=risk" replace />} />
              <Route path="/fund-os" element={<Navigate to="/copilot?tab=studio" replace />} />
              <Route path="/fund-os/terminal" element={<Navigate to="/copilot?tab=studio" replace />} />
              <Route path="/fund-os/terminal/:strategyId" element={<FundOSTerminalRedirect />} />
              <Route path="/pilot" element={<Navigate to="/copilot" replace />} />
              <Route path="/pilot/leaderboard" element={<Navigate to="/leaderboard" replace />} />
              <Route path="/pilot/p/:slug" element={<PilotProfileRedirect />} />
            </Routes>
            </Suspense>
          </main>
        </div>
        <Suspense fallback={null}>
          <ChatErrorBoundary onError={() => setChatFailed(true)}>
            {!chatFailed && (
              <AIChatbot
                isChatOpen={isChatOpen}
                setIsChatOpen={setIsChatOpen}
                chatWidth={chatWidth}
                setChatWidth={setChatWidth}
                isDesktop={isDesktop}
              />
            )}
          </ChatErrorBoundary>
        </Suspense>
        {/* Global Flux AI floating action button — lives outside the lazy
            chatbot chunk so it always renders, even if the chunk fails to
            load (stale deploy). Dispatches the same window event the drawer
            listens for. */}
        {!isChatOpen && (
          <button
            type="button"
            onClick={openFluxChat}
            data-testid="fluxai-fab"
            className="fixed bottom-6 right-6 z-[999] flex items-center justify-center gap-2 px-5 py-3.5 rounded-full shadow-lg hover:shadow-primary/30 hover:scale-105 transition-all duration-300 font-semibold"
            style={{
              background: 'var(--mf-accent, #E3B85F)',
              color: 'var(--mf-accent-fg, #1a1409)',
              boxShadow: '0 0 0 1px var(--mf-accent-border, rgba(227,184,95,0.35))',
            }}
            title="Ask Flux AI"
          >
            <Sparkles className="w-5 h-5" />
            <span className="text-sm hidden sm:inline">Flux AI</span>
          </button>
        )}
        <ScanlineOverlay />
        <Toaster position="top-right" />
      </div>
    </ErrorBoundary>
  );
}

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
