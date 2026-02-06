import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { AppSettings, EmbeddingModel, ModelInfo } from "@/lib/types"

export function useSettings() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [providerStatus, setProviderStatus] = useState("")
  const [modelStatus, setModelStatus] = useState("")
  const [indexStatus, setIndexStatus] = useState("")
  const [embeddingModels, setEmbeddingModels] = useState<EmbeddingModel[]>([])
  const [embeddingStatus, setEmbeddingStatus] = useState("")

  const loadEmbeddingModels = useCallback(async () => {
    try {
      const res = await api.get<{ models: EmbeddingModel[]; active_model: string }>(
        "/api/settings/embedding-models",
      )
      setEmbeddingModels(res.models)
    } catch {
      /* ignore on initial load */
    }
  }, [])

  const load = useCallback(async () => {
    const res = await api.get<AppSettings>("/api/settings")
    setSettings(res)
  }, [])

  useEffect(() => {
    load()
    loadEmbeddingModels()
  }, [load, loadEmbeddingModels])

  const saveProvider = useCallback(
    async (name: string, model: string, apiBase: string) => {
      await api.put("/api/settings/provider", {
        name,
        model,
        api_base: apiBase,
      })
      setModelStatus(`Saved: ${name} / ${model}`)
      await load()
    },
    [load],
  )

  const testConnection = useCallback(
    async (name: string, model: string, apiBase: string) => {
      setProviderStatus("Testing...")
      const res = await api.post<{ result: string }>("/api/settings/test-connection", {
        name,
        model,
        api_base: apiBase,
      })
      setProviderStatus(res.result)
    },
    [],
  )

  const refreshModels = useCallback(async (name: string, apiBase: string) => {
    const res = await api.post<{ models: string[]; status: string }>(
      "/api/settings/refresh-models",
      { name, api_base: apiBase },
    )
    return res
  }, [])

  const pingModel = useCallback(
    async (model: string, apiBase: string, signal?: AbortSignal) => {
      setModelStatus("Pinging model...")
      try {
        const res = await api.post<{ result: string }>("/api/settings/ping-model", {
          name: "",
          model,
          api_base: apiBase,
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

  const toggleFeature = useCallback(
    async (name: string, enabled: boolean) => {
      await api.put("/api/settings/features", { name, enabled })
      await load()
    },
    [load],
  )

  const addSource = useCallback(
    async (path: string) => {
      await api.post("/api/sources", { path })
      await load()
    },
    [load],
  )

  const removeSource = useCallback(
    async (path: string) => {
      await api.del("/api/sources", { path })
      await load()
    },
    [load],
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

  const reindex = useCallback(async () => {
    setIndexStatus("Indexing...")
    try {
      const res = await api.post<{ message: string }>("/api/index")
      setIndexStatus(res.message)
    } catch (e) {
      setIndexStatus(`Error: ${e}`)
    }
  }, [])

  const cancelIndex = useCallback(async () => {
    await api.post("/api/index/cancel")
    setIndexStatus("Cancelling...")
  }, [])

  const saveSystemPrompt = useCallback(
    async (prompt: string) => {
      await api.put("/api/settings/system-prompt", { prompt })
      await load()
    },
    [load],
  )

  const installEmbeddingModel = useCallback(
    async (modelId: string) => {
      setEmbeddingStatus(`Installing ${modelId}...`)
      try {
        await api.post("/api/settings/embedding-models/install", { model_id: modelId })
        setEmbeddingStatus(`Installed ${modelId}`)
        await loadEmbeddingModels()
      } catch (e) {
        setEmbeddingStatus(`Error: ${e}`)
      }
    },
    [loadEmbeddingModels],
  )

  const switchEmbeddingModel = useCallback(
    async (modelId: string) => {
      setEmbeddingStatus(`Switching to ${modelId} and reindexing...`)
      try {
        const res = await api.put<{ status: string; index_result: string }>(
          "/api/settings/embedding-models/switch",
          { model_id: modelId },
        )
        setEmbeddingStatus(res.index_result || "Switched successfully")
        await load()
        await loadEmbeddingModels()
      } catch (e) {
        setEmbeddingStatus(`Error: ${e}`)
      }
    },
    [load, loadEmbeddingModels],
  )

  return {
    settings,
    providerStatus,
    modelStatus,
    indexStatus,
    embeddingModels,
    embeddingStatus,
    saveProvider,
    testConnection,
    refreshModels,
    pingModel,
    fetchModelInfo,
    toggleFeature,
    addSource,
    removeSource,
    reindex,
    cancelIndex,
    saveSystemPrompt,
    installEmbeddingModel,
    switchEmbeddingModel,
  }
}
