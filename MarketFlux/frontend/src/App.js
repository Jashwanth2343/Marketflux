import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import TopNav from "@/components/TopNav";
import AIChatbot from "@/components/AIChatbot";
import ScanlineOverlay from "@/components/ScanlineOverlay";
import AuthCallback from "@/components/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import NewsFeed from "@/pages/NewsFeed";
import StockDetail from "@/pages/StockDetail";
import AIScreener from "@/pages/AIScreener";
import Portfolio from "@/pages/Portfolio";
import Auth from "@/pages/Auth";
import { Toaster } from "@/components/ui/sonner";

import { useState, useEffect } from "react";

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
          </Routes>
        </main>
      </div>
      <AIChatbot
        isChatOpen={isChatOpen}
        setIsChatOpen={setIsChatOpen}
        chatWidth={chatWidth}
        setChatWidth={setChatWidth}
        isDesktop={isDesktop}
      />
      <ScanlineOverlay />
      <Toaster position="top-right" />
    </div>
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
