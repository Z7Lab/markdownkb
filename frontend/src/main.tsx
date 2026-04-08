import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "./index.css"
import { App } from "./App.tsx"
import { Toaster } from "@/components/ui/sonner"
import { ErrorBoundary } from "@/components/error-boundary"
import { setApiKey } from "@/lib/api"

// Restore API key from localStorage (set during setup flow)
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
