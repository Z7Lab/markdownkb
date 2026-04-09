import { useCallback, useRef, useState } from "react"
import { api, getApiKey } from "@/lib/api"
import { parseSSEStream } from "@/lib/sse"
import type { ModelEntry, ModelInfo } from "@/lib/types"

export interface OllamaPullProgress {
  pulling: boolean
  model: string
  percent: number
  status: string
  error: string | null
  done: boolean
}

interface OllamaStatus {
  reachable: boolean
  api_base: string
  starter_models: { name: string; description: string }[]
}

export function useProviderSettings(reload: () => Promise<boolean>) {
  const [providerStatus, setProviderStatus] = useState("")
  const [modelStatus, setModelStatus] = useState("")
  const [pullProgress, setPullProgress] = useState<OllamaPullProgress>({
    pulling: false, model: "", percent: 0, status: "", error: null, done: false,
  })
  const pullAbortRef = useRef<AbortController | null>(null)

  const saveProvider = useCallback(
    async (name: string, model: string, apiBase: string, apiKey: string = "") => {
      const body: Record<string, string> = { name, model, api_base: apiBase }
      if (apiKey) body.api_key = apiKey
      await api.put("/api/settings/provider", body)
      setModelStatus(`Saved: ${name} / ${model}`)
      await reload()
    },
    [reload],
  )

  const testConnection = useCallback(
    async (name: string, model: string, apiBase: string, apiKey: string = "") => {
      setProviderStatus("Testing...")
      const res = await api.post<{ result: string }>("/api/settings/test-connection", {
        name,
        model,
        api_base: apiBase,
        api_key: apiKey,
      })
      setProviderStatus(res.result)
    },
    [],
  )

  const refreshModels = useCallback(async (name: string, apiBase: string) => {
    const res = await api.post<{ models: ModelEntry[]; status: string }>(
      "/api/settings/refresh-models",
      { name, api_base: apiBase },
    )
    return res
  }, [])

  const pingModel = useCallback(
    async (name: string, model: string, apiBase: string, apiKey: string = "", signal?: AbortSignal) => {
      setModelStatus("Pinging model...")
      try {
        const res = await api.post<{ result: string }>("/api/settings/ping-model", {
          name,
          model,
          api_base: apiBase,
          api_key: apiKey,
        }, signal)
        setModelStatus(res.result)
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          setModelStatus("")
        } else {
          setModelStatus(`Error: ${err}`)
        }
      }
    },
    [],
  )

  const saveLlmParams = useCallback(
    async (temperature: number, maxTokens: number, numCtx: number | null) => {
      await api.put("/api/settings/llm-params", {
        temperature,
        max_tokens: maxTokens,
        num_ctx: numCtx,
      })
      await reload()
    },
    [reload],
  )

  const fetchModelInfo = useCallback(
    async (model: string, apiBase: string) => {
      const res = await api.post<ModelInfo>("/api/settings/model-info", {
        model,
        api_base: apiBase,
      })
      return res
    },
    [],
  )

  const fetchOllamaStatus = useCallback(async () => {
    return api.get<OllamaStatus>("/api/settings/ollama/status")
  }, [])

  const pullOllamaModel = useCallback(
    async (modelName: string, apiBase: string = "") => {
      pullAbortRef.current?.abort()
      const controller = new AbortController()
      pullAbortRef.current = controller

      setPullProgress({ pulling: true, model: modelName, percent: 0, status: "Starting pull...", error: null, done: false })

      try {
        const headers: Record<string, string> = { "Content-Type": "application/json" }
        const key = getApiKey()
        if (key) headers["X-MarkdownKB-Key"] = key

        const res = await fetch("/api/settings/ollama/pull", {
          method: "POST",
          headers,
          body: JSON.stringify({ model_name: modelName, api_base: apiBase }),
          signal: controller.signal,
        })

        if (!res.ok) {
          const text = await res.text()
          setPullProgress((p) => ({ ...p, pulling: false, error: `HTTP ${res.status}: ${text}` }))
          return
        }

        const reader = res.body?.getReader()
        if (!reader) {
          setPullProgress((p) => ({ ...p, pulling: false, error: "No response body" }))
          return
        }

        await parseSSEStream(reader, (event, data) => {
          if (event === "progress") {
            setPullProgress((p) => ({
              ...p,
              status: data.status as string,
              percent: data.percent as number,
            }))
          } else if (event === "done") {
            setPullProgress((p) => ({ ...p, pulling: false, done: true, status: "success", percent: 100 }))
          } else if (event === "error") {
            setPullProgress((p) => ({ ...p, pulling: false, error: data.message as string }))
          }
        })
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setPullProgress((p) => ({ ...p, pulling: false, error: String(err) }))
        }
      }
    },
    [],
  )

  const cancelPull = useCallback(() => {
    pullAbortRef.current?.abort()
    pullAbortRef.current = null
    setPullProgress((p) => ({ ...p, pulling: false, status: "Cancelled" }))
  }, [])

  return {
    providerStatus,
    modelStatus,
    saveProvider,
    testConnection,
    refreshModels,
    pingModel,
    saveLlmParams,
    fetchModelInfo,
    pullProgress,
    pullOllamaModel,
    cancelPull,
    fetchOllamaStatus,
  }
}
