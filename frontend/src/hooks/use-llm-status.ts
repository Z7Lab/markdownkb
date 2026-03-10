import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"

export type LLMStatus = "online" | "offline" | "checking"

/** Minimal settings shape — only the fields we need for status checks */
interface LLMSettings {
  active_provider: string
  active_model: string
  active_api_base: string
}

/** Parse the test-connection response to extract model names */
function parseModels(result: string): string[] {
  // Format: "Connected to http://...\nAvailable models: model1, model2, ..."
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

  const checkStatus = useCallback(async () => {
    try {
      const settings = await api.get<LLMSettings>("/api/settings")

      setProvider(settings.active_provider)

      if (!settings.active_model) {
        setStatus("offline")
        setAvailableModels([])
        return
      }

      // Backend resolves API key from env/yaml — no need to send it
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
    } catch {
      setStatus("offline")
      setAvailableModels([])
      setLastChecked(new Date())
    }
  }, [])

  useEffect(() => {
    const interval = setInterval(checkStatus, 30000)
    return () => clearInterval(interval)
  }, [checkStatus])

  // Initial status check on mount — separate from interval setup
  // eslint-disable-next-line react-hooks/set-state-in-effect -- initial async fetch on mount
  useEffect(() => { checkStatus() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return { status, lastChecked, availableModels, provider, checkStatus }
}
