import { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Database, X } from "lucide-react"
import { api } from "@/lib/api"

const DISMISS_KEY = "markdownkb-embedding-nudge-dismissed"

export function EmbeddingSetupNudge({ onNavigateSettings }: { onNavigateSettings: () => void }) {
  const [missing, setMissing] = useState(false)
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem(DISMISS_KEY) === "true",
  )

  useEffect(() => {
    api.get<{ embedding_model_missing?: boolean }>("/api/v1/health")
      .then((data) => {
        if (data.embedding_model_missing) setMissing(true)
      })
      .catch(() => { console.warn("Failed to check embedding health") })
  }, [])

  const handleDismiss = useCallback(() => {
    setDismissed(true)
    sessionStorage.setItem(DISMISS_KEY, "true")
  }, [])

  if (dismissed || !missing) return null

  return (
    <div className="bg-amber-50 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-800 px-6 py-3">
      <div className="flex items-center gap-3 mx-auto max-w-3xl">
        <Database className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0" />
        <p className="text-sm text-amber-800 dark:text-amber-200 flex-1">
          No embedding model installed. Download one to enable indexing and search.
        </p>
        <Button variant="outline" size="sm" onClick={onNavigateSettings}>
          Set Up
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 shrink-0 text-amber-600 dark:text-amber-400 hover:text-amber-800 hover:bg-amber-100 dark:hover:bg-amber-900/50"
          onClick={handleDismiss}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
