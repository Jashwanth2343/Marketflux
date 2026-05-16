import React, { useState, useEffect, lazy, Suspense } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import TopNav from "@/components/TopNav";

const AIChatbot = lazy(() => import("@/components/AIChatbot"));
import ScanlineOverlay from "@/components/ScanlineOverlay";
import AuthCallback from "@/components/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import Intelligence from "@/pages/Intelligence";
import Copilot from "@/pages/Copilot";
import PortfolioRisk from "@/pages/PortfolioRisk";
import Backtest from "@/pages/Backtest";
import StockDetail from "@/pages/StockDetail";
import ThesisNew from "@/pages/ThesisNew";
import ThesisWorkspace from "@/pages/ThesisWorkspace";
import ThesisTradeLab from "@/pages/ThesisTradeLab";
import Auth from "@/pages/Auth";
import PilotLeaderboard from "@/pages/PilotLeaderboard";
import PilotPublicProfile from "@/pages/PilotPublicProfile";
import { Toaster } from "@/components/ui/sonner";

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

function AppRouter() {
  const location = useLocation();
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatWidth, setChatWidth] = useState(380);
  const [isDesktop, setIsDesktop] = useState(window.innerWidth >= 1024);

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
            <Routes>
              {/* Core pages */}
              <Route path="/" element={<Dashboard />} />
              <Route path="/intelligence" element={<Intelligence />} />
              <Route path="/intelligence/thesis/new" element={<ThesisNew />} />
              <Route path="/intelligence/thesis/:thesisId" element={<ThesisWorkspace />} />
              <Route path="/intelligence/thesis/:thesisId/trade-lab" element={<ThesisTradeLab />} />
              <Route path="/copilot" element={<Copilot />} />
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
              <Route path="/risk" element={<Navigate to="/portfolio?tab=risk" replace />} />
              <Route path="/fund-os" element={<Navigate to="/copilot?tab=studio" replace />} />
              <Route path="/fund-os/terminal" element={<Navigate to="/copilot?tab=studio" replace />} />
              <Route path="/fund-os/terminal/:strategyId" element={<Navigate to="/copilot?tab=studio" replace />} />
              <Route path="/pilot" element={<Navigate to="/copilot" replace />} />
              <Route path="/pilot/leaderboard" element={<Navigate to="/leaderboard" replace />} />
              <Route path="/pilot/p/:slug" element={<Navigate to="/leaderboard/p/:slug" replace />} />
            </Routes>
          </main>
        </div>
        <Suspense fallback={null}>
        <AIChatbot
          isChatOpen={isChatOpen}
          setIsChatOpen={setIsChatOpen}
          chatWidth={chatWidth}
          setChatWidth={setChatWidth}
          isDesktop={isDesktop}
        />
        </Suspense>
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
