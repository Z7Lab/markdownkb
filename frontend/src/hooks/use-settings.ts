import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react"
import { createElement } from "react"
import { api, retryWithBackoff } from "@/lib/api"
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
  const [loadError, setLoadError] = useState<string | null>(null)

  // Every mutation calls load() after its PUT/POST/DELETE to keep the local state
  // in sync with the server. A full refetch is intentional: settings objects are
  // small, mutations are infrequent, and it avoids stale-cache bugs from partial
  // optimistic updates (e.g. a plugin toggle that also affects dependent settings).
  const load = useCallback(async (): Promise<boolean> => {
    try {
      const res = await api.get<AppSettings>("/api/settings")
      setSettings(res)
      setLoadError(null)
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      console.error("Failed to load settings:", message)
      setLoadError(message)
      return false
    }
  }, [])

  // Initial load with retry
  useEffect(() => {
    return retryWithBackoff(() => load())
  }, [load])

  // Domain hooks
  const provider = useProviderSettings(load)
  const embedding = useEmbeddingSettings(load)

  // Section-aware toggle actions
  const toggleCore = useCallback(
    async (name: string, enabled: boolean) => {
      await api.put("/api/settings/core", { name, enabled })
      await load()
    },
    [load],
  )

  const toggleMcpFlag = useCallback(
    async (name: string, enabled: boolean) => {
      await api.put("/api/settings/mcp-flags", { name, enabled })
      await load()
    },
    [load],
  )

  const togglePlugin = useCallback(
    async (name: string, enabled: boolean) => {
      await api.put(`/api/settings/plugins/${name}/enabled`, { name, enabled })
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

  const updateSource = useCallback(
    async (path: string, changes: { writable?: boolean; versioned?: boolean }) => {
      await api.patch("/api/sources", { path, ...changes })
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
      const result = await api.post<{ docker_restart_required?: boolean; path_not_found?: boolean; message?: string }>(
        "/api/project-roots", { path, include, exclude }
      )
      await load()
      return result
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
    loadError,
    reload: load,
    // Provider
    ...provider,
    // Embedding
    ...embedding,
    // Sources
    addSource,
    removeSource,
    updateSource,
    addIgnorePattern,
    removeIgnorePattern,
    // Project Roots
    addProjectRoot,
    removeProjectRoot,
    updateProjectRoot,
    // Feature toggles
    toggleCore,
    toggleMcpFlag,
    togglePlugin,
    toggleIntelligentSearch,
    saveSystemPrompt,
    saveSearchSummaryPrompt,
    saveRetrievalSettings,
    setLogLevel,
  }
}
