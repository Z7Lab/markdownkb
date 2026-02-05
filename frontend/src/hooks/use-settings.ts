import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { AppSettings, ModelInfo } from "@/lib/types"

export function useSettings() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [providerStatus, setProviderStatus] = useState("")
  const [modelStatus, setModelStatus] = useState("")
  const [indexStatus, setIndexStatus] = useState("")

  const load = useCallback(async () => {
    const res = await api.get<AppSettings>("/api/settings")
    setSettings(res)
  }, [])

  useEffect(() => {
    load()
  }, [load])

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

  return {
    settings,
    providerStatus,
    modelStatus,
    indexStatus,
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
  }
}
