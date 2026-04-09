import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "./index.css"
import { App } from "./App.tsx"
import { Toaster } from "@/components/ui/sonner"
import { ErrorBoundary } from "@/components/error-boundary"
import { setApiKey } from "@/lib/api"

// Restore API key from localStorage (set during the setup-banner flow).
// Trade-off: localStorage is readable by any JS on the same origin, so XSS
// could expose it. This is an accepted risk for a local/LAN deployment
// without server-side session cookies. See SECURITY.md for the rationale.
const storedKey = localStorage.getItem("markdownkb-api-key")
if (storedKey) setApiKey(storedKey)

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary fallbackMessage="The application crashed unexpectedly">
      <App />
      <Toaster />
    </ErrorBoundary>
  </StrictMode>,
)
