import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react"
import { createElement } from "react"
import { api } from "@/lib/api"
import type { AppSettings, EmbeddingModel, ModelInfo } from "@/lib/types"

type SettingsValue = ReturnType<typeof useSettingsInternal>

const SettingsContext = createContext<SettingsValue | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const value = useSettingsInternal()
  return createElement(SettingsContext.Provider, { value }, children)
}

export function useSettings(): SettingsValue {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error("useSettings must be used within SettingsProvider")
  return ctx
}

function useSettingsInternal() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [providerStatus, setProviderStatus] = useState("")
  const [modelStatus, setModelStatus] = useState("")
  const [indexStatus, setIndexStatus] = useState("")
  const [embeddingModels, setEmbeddingModels] = useState<EmbeddingModel[]>([])
  const [embeddingStatus, setEmbeddingStatus] = useState("")
  const [embeddingSwitching, setEmbeddingSwitching] = useState(false)

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

  const load = useCallback(async (): Promise<boolean> => {
    try {
      const res = await api.get<AppSettings>("/api/settings")
      setSettings(res)
      return true
    } catch (err) {
      console.warn("Failed to load settings:", err)
      return false
    }
  }, [])

  // Initial load with retry on failure
  useEffect(() => {
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let retryCount = 0
    const MAX_RETRIES = 10

    const loadWithRetry = async () => {
      const success = await load()

      // If load failed and we haven't exceeded max retries, retry in 2 seconds
      if (!success && retryCount < MAX_RETRIES) {
        retryCount++
        retryTimer = setTimeout(loadWithRetry, 2000)
      }
    }

    loadWithRetry()
    loadEmbeddingModels()
    // Check if a background reindex is already running (e.g. page refresh)
    api.get<{
      running: boolean
      progress: number
      message: string
      result: string
    }>("/api/settings/embedding-models/status").then((st) => {
      if (st.running) {
        setEmbeddingSwitching(true)
        const pct = Math.round(st.progress * 100)
        setEmbeddingStatus(`[${pct}%] ${st.message}`)
        // Start polling
        switchPollRef.current = setInterval(async () => {
          try {
            const s = await api.get<{
              running: boolean
              progress: number
              message: string
              result: string
            }>("/api/settings/embedding-models/status")
            if (s.running) {
              const p = Math.round(s.progress * 100)
              setEmbeddingStatus(`[${p}%] ${s.message}`)
            } else {
              if (switchPollRef.current) clearInterval(switchPollRef.current)
              switchPollRef.current = null
              setEmbeddingSwitching(false)
              setEmbeddingStatus(s.result || "Reindex complete")
              load()
              loadEmbeddingModels()
            }
          } catch {
            if (switchPollRef.current) clearInterval(switchPollRef.current)
            switchPollRef.current = null
            setEmbeddingSwitching(false)
            setEmbeddingStatus("Lost connection during reindex")
          }
        }, 1500)
      }
    }).catch(() => { /* ignore */ })

    return () => {
      if (retryTimer) clearTimeout(retryTimer)
      // Clean up any active polling interval on unmount
      if (switchPollRef.current) {
        clearInterval(switchPollRef.current)
        switchPollRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run on mount

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

  const toggleIntelligentSearch = useCallback(
    async (enabled: boolean) => {
      await api.put("/api/settings/intelligent-search", { name: "intelligent_search", enabled })
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

  const addIgnorePattern = useCallback(
    async (pattern: string) => {
      await api.post("/api/ignore-patterns", { pattern })
      await load()
    },
    [load],
  )

  const removeIgnorePattern = useCallback(
    async (pattern: string) => {
      await api.del("/api/ignore-patterns", { pattern })
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

  const reindex = useCallback(async (force = false) => {
    if (!force) {
      setIndexStatus("Indexing...")
      try {
        const res = await api.post<{ message: string }>("/api/index")
        setIndexStatus(res.message)
      } catch (e) {
        setIndexStatus(`Error: ${e}`)
      }
      return
    }

    setEmbeddingStatus("Force reindexing all files...")
    setEmbeddingSwitching(true)
    try {
      await api.post("/api/index", { force: true })

      switchPollRef.current = setInterval(async () => {
        try {
          const st = await api.get<{
            running: boolean
            progress: number
            message: string
            result: string
          }>("/api/settings/embedding-models/status")
          if (st.running) {
            const pct = Math.round(st.progress * 100)
            setEmbeddingStatus(`[${pct}%] ${st.message}`)
          } else {
            if (switchPollRef.current) clearInterval(switchPollRef.current)
            switchPollRef.current = null
            setEmbeddingSwitching(false)
            setEmbeddingStatus(st.result || "Reindex complete")
            await load()
          }
        } catch {
          if (switchPollRef.current) clearInterval(switchPollRef.current)
          switchPollRef.current = null
          setEmbeddingSwitching(false)
          setEmbeddingStatus("Lost connection during reindex")
        }
      }, 1500)
    } catch (e) {
      setEmbeddingSwitching(false)
      setEmbeddingStatus(`Error: ${e}`)
    }
  }, [load])

  const cancelIndex = useCallback(async () => {
    await api.post("/api/index/cancel")
    if (switchPollRef.current) {
      clearInterval(switchPollRef.current)
      switchPollRef.current = null
    }
    setEmbeddingSwitching(false)
    setEmbeddingStatus("Cancelled")
    setIndexStatus("Cancelled")
  }, [])

  const saveSystemPrompt = useCallback(
    async (prompt: string) => {
      await api.put("/api/settings/system-prompt", { prompt })
      await load()
    },
    [load],
  )

  const saveSearchSummaryPrompt = useCallback(
    async (prompt: string) => {
      await api.put("/api/settings/search-summary-prompt", { prompt })
      await load()
    },
    [load],
  )

  const saveRetrievalSettings = useCallback(
    async (settings: {
      top_k: number
      score_threshold: number
      hybrid_search: boolean
      bm25_weight: number
    }) => {
      await api.put("/api/settings/retrieval", settings)
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

  const switchPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      if (switchPollRef.current) clearInterval(switchPollRef.current)
    }
  }, [])

  const switchEmbeddingModel = useCallback(
    async (modelId: string) => {
      setEmbeddingStatus(`Switching to ${modelId}...`)
      setEmbeddingSwitching(true)
      try {
        await api.put<{ status: string }>(
          "/api/settings/embedding-models/switch",
          { model_id: modelId },
        )

        // Refresh model list immediately to show new active model
        await loadEmbeddingModels()

        // Poll for background reindex progress
        switchPollRef.current = setInterval(async () => {
          try {
            const st = await api.get<{
              running: boolean
              progress: number
              message: string
              result: string
            }>("/api/settings/embedding-models/status")
            if (st.running) {
              const pct = Math.round(st.progress * 100)
              setEmbeddingStatus(`[${pct}%] ${st.message}`)
            } else {
              if (switchPollRef.current) clearInterval(switchPollRef.current)
              switchPollRef.current = null
              setEmbeddingSwitching(false)
              setEmbeddingStatus(st.result || "Switched successfully")
              await load()
              await loadEmbeddingModels()
            }
          } catch {
            if (switchPollRef.current) clearInterval(switchPollRef.current)
            switchPollRef.current = null
            setEmbeddingSwitching(false)
            setEmbeddingStatus("Lost connection during reindex")
          }
        }, 1500)
      } catch (e) {
        setEmbeddingSwitching(false)
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
    embeddingSwitching,
    saveProvider,
    testConnection,
    refreshModels,
    pingModel,
    fetchModelInfo,
    toggleFeature,
    toggleIntelligentSearch,
    addSource,
    removeSource,
    addIgnorePattern,
    removeIgnorePattern,
    reindex,
    cancelIndex,
    saveSystemPrompt,
    saveSearchSummaryPrompt,
    saveRetrievalSettings,
    installEmbeddingModel,
    switchEmbeddingModel,
  }
}
