import { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Cpu, X } from "lucide-react"

const DISMISS_KEY = "mdkb-llm-nudge-dismissed"

interface LlmHealth {
  configured: boolean
  reachable: boolean
  provider: string
  model: string
  api_base: string
}

export function LlmSetupNudge({ onNavigateSettings }: { onNavigateSettings: () => void }) {
  const [health, setHealth] = useState<LlmHealth | null>(null)
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(DISMISS_KEY) === "true",
  )

  useEffect(() => {
    fetch("/api/health/llm")
      .then((r) => r.json())
      .then((data: LlmHealth) => setHealth(data))
      .catch(() => {})
  }, [])

  const handleDismiss = useCallback(() => {
    setDismissed(true)
    sessionStorage.setItem(DISMISS_KEY, "true")
  }, [])

  if (dismissed || !health) return null

  // Determine what to show
  let message: string | null = null
  let action = "Set Up LLM"

  if (!health.configured) {
    message = "No LLM provider configured. Set up Ollama (free, local) or point to any OpenAI-compatible server to start chatting."
    action = "Configure LLM"
  } else if (!health.reachable && health.provider.toLowerCase().includes("ollama")) {
    message = `Cannot reach Ollama at ${health.api_base || "default address"}. Make sure Ollama is running.`
    action = "Check Settings"
  }

  if (!message) return null

  return (
    <div className="bg-blue-50 dark:bg-blue-950/30 border-b border-blue-200 dark:border-blue-800 px-6 py-3">
      <div className="flex items-center gap-3 mx-auto max-w-3xl">
        <Cpu className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0" />
        <p className="text-sm text-blue-800 dark:text-blue-200 flex-1">{message}</p>
        <Button variant="outline" size="sm" onClick={onNavigateSettings}>
          {action}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 shrink-0 text-blue-600 dark:text-blue-400 hover:text-blue-800 hover:bg-blue-100 dark:hover:bg-blue-900/50"
          onClick={handleDismiss}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
