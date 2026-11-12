import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Force dark mode
document.documentElement.classList.add('dark');

console.log('[MarketFlux] frontend ready');

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <App />
);
