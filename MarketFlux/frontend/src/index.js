import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Force dark mode
document.documentElement.classList.add('dark');

// Boot marker — lets us confirm at a glance that the latest build is live.
// (Supabase auth fetch hardening now lives in src/lib/supabase.js, which routes
// auth requests through a pristine native fetch to bypass emergent-main.js's
// body-draining network monitor.)
console.log('[MarketFlux] build: native-fetch v4');

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <App />
);
