import { useCallback, useEffect, useState } from "react"
import { useLocation } from "wouter"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { ShieldAlert, X } from "lucide-react"

interface HealthResponse {
  auth_enabled: boolean
  network_exposed: boolean
}

const DISMISS_KEY = "markdownkb-setup-banner-dismissed"

export function SetupBanner({ forceShow = false }: { forceShow?: boolean }) {
  const [needsSetup, setNeedsSetup] = useState(false)
  const [dismissed, setDismissed] = useState(
    () => !forceShow && sessionStorage.getItem(DISMISS_KEY) === "true",
  )
  const [, setLocation] = useLocation()

  useEffect(() => {
    api.get<HealthResponse>("/api/v1/health")
      .then((data) => {
        if (!data.auth_enabled && data.network_exposed) {
          setNeedsSetup(true)
        }
      })
      .catch((e) => { console.warn("Setup banner: failed to check health", e) })
  }, [])

  const handleDismiss = useCallback(() => {
    setDismissed(true)
    sessionStorage.setItem(DISMISS_KEY, "true")
  }, [])

  if (!needsSetup || dismissed) return null

  return (
    <div className="bg-amber-50 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-800 px-6 py-3">
      <div className="flex items-center gap-3 mx-auto max-w-3xl">
        <ShieldAlert className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0" />
        <p className="text-sm text-amber-800 dark:text-amber-200 flex-1">
          This instance is accessible on your network without authentication.
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setLocation("/settings/security")}
        >
          Set up security
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 shrink-0 text-amber-700 dark:text-amber-300 hover:text-amber-900 hover:bg-amber-100 dark:hover:bg-amber-900/50"
          aria-label="Dismiss security warning"
          onClick={handleDismiss}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
