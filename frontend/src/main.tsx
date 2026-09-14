import "./lib/fonts";
import "./index.css";
import "katex/dist/katex.min.css";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { TooltipProvider } from "./components/ui/tooltip";
import { captureWebVitals } from "./utils/web-vitals";

captureWebVitals({
  debug: import.meta.env.DEV,
  // Add this when the metrics service is available.
  // endpoint: "/api/metrics/vitals",
});

const root = document.getElementById("root");
if (!root) {
  throw new Error("Root element not found");
}

createRoot(root).render(
  <StrictMode>
    <TooltipProvider>
      <App />
    </TooltipProvider>
  </StrictMode>,
);
