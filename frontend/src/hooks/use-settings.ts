import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react"
import { createElement } from "react"
import { api } from "@/lib/api"
import type { AppSettings } from "@/lib/types"
import { useProviderSettings } from "./use-provider-settings"
import { useEmbeddingSettings } from "./use-embedding-settings"

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

  // Initial load with retry
  useEffect(() => {
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let retryCount = 0
    const MAX_RETRIES = 10

    const loadWithRetry = async () => {
      const success = await load()
      if (!success && retryCount < MAX_RETRIES) {
        retryCount++
        retryTimer = setTimeout(loadWithRetry, 2000)
      }
    }

    loadWithRetry()

    return () => { if (retryTimer) clearTimeout(retryTimer) }
  }, [load])

  // Domain hooks
  const provider = useProviderSettings(load)
  const embedding = useEmbeddingSettings(load)

  // Simple settings actions that just save + reload
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
    async (path: string, cleanup = false) => {
      await api.del("/api/sources", { path, cleanup })
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

  const addProjectRoot = useCallback(
    async (path: string, include: string[], exclude: string[]) => {
      await api.post("/api/project-roots", { path, include, exclude })
      await load()
    },
    [load],
  )

  const removeProjectRoot = useCallback(
    async (path: string, cleanup = false) => {
      await api.del("/api/project-roots", { path, cleanup })
      await load()
    },
    [load],
  )

  const updateProjectRoot = useCallback(
    async (path: string, include: string[], exclude: string[]) => {
      await api.put("/api/project-roots", { path, include, exclude })
      await load()
    },
    [load],
  )

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
    async (s: {
      top_k: number
      score_threshold: number
      hybrid_search: boolean
      bm25_weight: number
    }) => {
      await api.put("/api/settings/retrieval", s)
      await load()
    },
    [load],
  )

  const setLogLevel = useCallback(
    async (level: string) => {
      await api.put("/api/settings/log-level", { level })
      await load()
    },
    [load],
  )

  return {
    settings,
    // Provider
    ...provider,
    // Embedding
    ...embedding,
    // Sources
    addSource,
    removeSource,
    addIgnorePattern,
    removeIgnorePattern,
    // Project Roots
    addProjectRoot,
    removeProjectRoot,
    updateProjectRoot,
    // Features & config
    toggleFeature,
    toggleIntelligentSearch,
    saveSystemPrompt,
    saveSearchSummaryPrompt,
    saveRetrievalSettings,
    setLogLevel,
  }
}
