import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"

export type LLMStatus = "online" | "offline" | "checking"

/** Lightweight health check response from /api/health/llm */
interface LLMHealth {
  provider: string
  model: string
  configured: boolean
}

/** Minimal settings shape — only the fields we need for full status checks */
interface LLMSettings {
  active_provider: string
  active_model: string
  active_api_base: string
}

/** Parse the test-connection response to extract model names */
function parseModels(result: string): string[] {
  const modelsLine = result.split("\n").find(line => line.includes("Available models:"))
  if (!modelsLine) return []
  const after = modelsLine.split("Available models:")[1]
  if (!after) return []
  return after.trim().split(", ").map(m => m.trim()).filter(Boolean)
}

/** Determine connection status from test-connection response */
function isSuccessResult(result: string): boolean {
  return result.startsWith("Connected") || result.includes("Available models")
}

export function useLLMStatus() {
  const [status, setStatus] = useState<LLMStatus>("checking")
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [provider, setProvider] = useState<string>("")
  const fullCheckDone = useRef(false)

  /** Lightweight poll — checks /api/health/llm (no provider API calls) */
  const pollStatus = useCallback(async () => {
    try {
      const health = await api.get<LLMHealth>("/api/health/llm")
      setProvider(health.provider)
      if (!health.configured) {
        setStatus("offline")
        setAvailableModels([])
      }
      // If configured, keep last known status from the full check
    } catch {
      setStatus("offline")
    }
  }, [])

  /** Full status check — calls test-connection (heavy, used once on mount + explicit refresh) */
  const checkStatus = useCallback(async () => {
    try {
      const settings = await api.get<LLMSettings>("/api/settings")
      setProvider(settings.active_provider)

      if (!settings.active_model) {
        setStatus("offline")
        setAvailableModels([])
        fullCheckDone.current = true
        return
      }

      const result = await api.post<{ result: string }>("/api/settings/test-connection", {
        name: settings.active_provider,
        model: settings.active_model,
        api_base: settings.active_api_base,
        api_key: "",
      })

      const connected = isSuccessResult(result.result)
      setAvailableModels(connected ? parseModels(result.result) : [])
      setStatus(connected ? "online" : "offline")
      setLastChecked(new Date())
      fullCheckDone.current = true
    } catch {
      setStatus("offline")
      setAvailableModels([])
      setLastChecked(new Date())
      fullCheckDone.current = true
    }
  }, [])

  // Lightweight poll every 30s — no heavy API calls to provider
  useEffect(() => {
    const interval = setInterval(pollStatus, 30000)
    return () => clearInterval(interval)
  }, [pollStatus])

  // Full status check once on mount
  useEffect(() => { checkStatus() }, [checkStatus])

  return { status, lastChecked, availableModels, provider, checkStatus }
}
