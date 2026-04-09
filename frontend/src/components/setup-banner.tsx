import { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { api, setApiKey } from "@/lib/api"
import { ShieldAlert, Copy, Check, X } from "lucide-react"

interface HealthResponse {
  auth_enabled: boolean
  network_exposed: boolean
}

const DISMISS_KEY = "markdownkb-setup-banner-dismissed"

export function SetupBanner({ forceShow = false }: { forceShow?: boolean }) {
  const [needsSetup, setNeedsSetup] = useState(false)
  const [generatedKey, setGeneratedKey] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [copied, setCopied] = useState(false)
  const [dismissed, setDismissed] = useState(
    () => !forceShow && sessionStorage.getItem(DISMISS_KEY) === "true",
  )

  useEffect(() => {
    api.get<HealthResponse>("/api/health")
      .then((data) => {
        if (!data.auth_enabled && data.network_exposed) {
          setNeedsSetup(true)
        }
      })
      .catch(() => {})
  }, [])

  const handleGenerate = useCallback(async () => {
    setGenerating(true)
    try {
      const data = await api.post<{ api_key: string }>("/api/setup/generate-key")
      setGeneratedKey(data.api_key)
      setApiKey(data.api_key)
      // Store in localStorage so the key survives page refresh.
      // Trade-off: localStorage is accessible to JS on the same origin, so XSS
      // could expose it. This is acceptable for a local/LAN deployment without
      // a session cookie infrastructure. See SECURITY.md for details.
      localStorage.setItem("markdownkb-api-key", data.api_key)
    } catch {
      // If it fails, the banner stays visible for retry
    } finally {
      setGenerating(false)
    }
  }, [])

  const handleCopy = useCallback(() => {
    if (!generatedKey) return
    navigator.clipboard.writeText(generatedKey).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [generatedKey])

  const handleDismiss = useCallback(() => {
    setDismissed(true)
    sessionStorage.setItem(DISMISS_KEY, "true")
  }, [])

  if (!needsSetup || dismissed) return null

  // Key generated — show it once
  if (generatedKey) {
    return (
      <div className="bg-green-50 dark:bg-green-950/30 border-b border-green-200 dark:border-green-800 px-6 py-3">
        <div className="flex items-start gap-3 mx-auto max-w-3xl">
          <Check className="h-5 w-5 text-green-600 dark:text-green-400 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0 space-y-2">
            <p className="text-sm font-medium text-green-800 dark:text-green-200">
              API key generated. Save it now — it won't be shown again.
            </p>
            <div className="flex items-center gap-2">
              <code className="text-xs bg-green-100 dark:bg-green-900/50 px-2 py-1 rounded font-mono break-all">
                {generatedKey}
              </code>
              <Button
                variant="outline"
                size="sm"
                className="h-7 px-2 shrink-0"
                onClick={handleCopy}
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              </Button>
            </div>
            <p className="text-xs text-green-700 dark:text-green-300">
              Use the <code className="font-mono">X-MarkdownKB-Key</code> header for API requests.
              This browser session is already configured.
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 shrink-0 text-green-700 dark:text-green-300 hover:text-green-900 hover:bg-green-100 dark:hover:bg-green-900/50"
            onClick={handleDismiss}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    )
  }

  // No key yet — show warning
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
          onClick={handleGenerate}
          disabled={generating}
        >
          {generating ? "Generating..." : "Generate API Key"}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 shrink-0 text-red-600 dark:text-red-400 hover:text-red-800 hover:bg-red-50 dark:hover:bg-red-950/50"
          onClick={handleDismiss}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
