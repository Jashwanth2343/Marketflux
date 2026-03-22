import React, { useState, useEffect, lazy, Suspense } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import TopNav from "@/components/TopNav";

const AIChatbot = lazy(() => import("@/components/AIChatbot"));
import ScanlineOverlay from "@/components/ScanlineOverlay";
import AuthCallback from "@/components/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import NewsFeed from "@/pages/NewsFeed";
import StockDetail from "@/pages/StockDetail";
import AIScreener from "@/pages/AIScreener";
import Portfolio from "@/pages/Portfolio";
import Auth from "@/pages/Auth";
import ResearchCenter from "@/pages/ResearchCenter";
import MacroDashboard from "@/pages/MacroDashboard";
import RiskConsole from "@/pages/RiskConsole";
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

  // Check URL fragment for session_id synchronously during render
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  // Calculate dynamic margin for desktop chat side panel
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
              <Route path="/" element={<Dashboard />} />
              <Route path="/news" element={<NewsFeed />} />
              <Route path="/screener" element={<AIScreener />} />
              <Route path="/stock/:ticker" element={<StockDetail />} />
              <Route path="/portfolio" element={<Portfolio />} />
              <Route path="/auth" element={<Auth />} />
              <Route path="/research" element={<ResearchCenter />} />
              <Route path="/macro" element={<MacroDashboard />} />
              <Route path="/risk" element={<RiskConsole />} />
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
