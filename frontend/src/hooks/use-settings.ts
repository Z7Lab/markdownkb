import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { AppSettings } from "@/lib/types"

export function useSettings() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [status, setStatus] = useState("")
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
      setStatus(`Saved: ${name} / ${model}`)
      await load()
    },
    [load],
  )

  const testConnection = useCallback(
    async (name: string, model: string, apiBase: string) => {
      setStatus("Testing...")
      const res = await api.post<{ result: string }>("/api/settings/test-connection", {
        name,
        model,
        api_base: apiBase,
      })
      setStatus(res.result)
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
    status,
    indexStatus,
    saveProvider,
    testConnection,
    refreshModels,
    toggleFeature,
    addSource,
    removeSource,
    reindex,
    cancelIndex,
  }
}
