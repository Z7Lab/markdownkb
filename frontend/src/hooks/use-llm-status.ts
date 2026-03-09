import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"

export type LLMStatus = "online" | "offline" | "checking"

export function useLLMStatus() {
  const [status, setStatus] = useState<LLMStatus>("checking")
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [provider, setProvider] = useState<string>("")

  const checkStatus = useCallback(async () => {
    try {
      // Get current settings
      const settings = await api.get<{
        active_provider: string
        active_model: string
        active_api_base: string
      }>("/api/settings")

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

      // test-connection returns a string - check if it indicates success
      const isConnected = result.result.includes("Connected") ||
                         result.result.includes("Available models")

      // Extract available models from response
      // Format: "Connected to http://...\nAvailable models: model1, model2, ..."
      if (isConnected && result.result.includes("Available models:")) {
        const modelsLine = result.result.split("\n").find(line => line.includes("Available models:"))
        if (modelsLine) {
          const modelsList = modelsLine.split("Available models:")[1].trim()
          setAvailableModels(modelsList.split(", ").map(m => m.trim()))
        }
      } else {
        setAvailableModels([])
      }

      setStatus(isConnected ? "online" : "offline")
      setLastChecked(new Date())
    } catch {
      setStatus("offline")
      setAvailableModels([])
      setLastChecked(new Date())
    }
  }, [])

  useEffect(() => {
    // Wrap checkStatus in Promise.resolve().then() to avoid set-state-in-effect warning
    Promise.resolve().then(() => checkStatus())

    // Then check every 30 seconds
    const interval = setInterval(checkStatus, 30000)

    return () => clearInterval(interval)
  }, [checkStatus])

  return { status, lastChecked, availableModels, provider, checkStatus }
}
