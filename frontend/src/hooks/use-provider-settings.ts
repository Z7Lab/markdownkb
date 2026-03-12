import { useCallback, useState } from "react"
import { api } from "@/lib/api"
import type { ModelEntry, ModelInfo } from "@/lib/types"

export function useProviderSettings(reload: () => Promise<boolean>) {
  const [providerStatus, setProviderStatus] = useState("")
  const [modelStatus, setModelStatus] = useState("")

  const saveProvider = useCallback(
    async (name: string, model: string, apiBase: string, apiKey: string = "") => {
      await api.put("/api/settings/provider", {
        name,
        model,
        api_base: apiBase,
        api_key: apiKey,
      })
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

  return {
    providerStatus,
    modelStatus,
    saveProvider,
    testConnection,
    refreshModels,
    pingModel,
    saveLlmParams,
    fetchModelInfo,
  }
}
