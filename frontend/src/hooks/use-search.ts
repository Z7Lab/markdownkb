import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { streamSearchSummary } from "@/lib/sse"
import { toast } from "sonner"
import type { PaginatedResponse, SavedSearch, SearchResult, SearchResponse, CompareResponse, SearchVersion, ScoreChange } from "@/lib/types"

export function useSearch(scopeIds?: string | null, adHocTags?: string[] | null) {
  const [query, setQuery] = useState("")
  const [folder, setFolder] = useState<string | null>(null)
  const [tag, setTag] = useState<string | null>(null)
  const [results, setResults] = useState<SearchResult[]>([])
  const [folders, setFolders] = useState<string[]>([])
  const [tags, setTags] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingHistorical, setLoadingHistorical] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Search history
  const [searches, setSearches] = useState<SavedSearch[]>([])
  const [activeSearchId, setActiveSearchId] = useState<string | null>(null)

  // Historical search metadata
  const [isHistorical, setIsHistorical] = useState(false)
  const [resultsChanged, setResultsChanged] = useState(false)
  const [missingFiles, setMissingFiles] = useState<string[]>([])
  const [newFiles, setNewFiles] = useState<string[]>([])
  const [scoreChanges, setScoreChanges] = useState<ScoreChange[]>([])
  const [storedResultCount, setStoredResultCount] = useState<number | null>(null)
  const [currentResultCount, setCurrentResultCount] = useState<number | null>(null)
  const [createdAt, setCreatedAt] = useState<string | null>(null)
  const [versionCount, setVersionCount] = useState(0)

  // AI summary
  const [summary, setSummary] = useState("")
  const [summarySources, setSummarySources] = useState<string[]>([])
  const [isSummarizing, setIsSummarizing] = useState(false)
  const summaryControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let retryCount = 0
    const MAX_RETRIES = 10

    const loadWithRetry = async () => {
      try {
        const [foldersRes, tagsRes, searchesRes] = await Promise.all([
          api.get<PaginatedResponse<string>>("/api/folders"),
          api.get<PaginatedResponse<string>>("/api/tags"),
          api.get<PaginatedResponse<SavedSearch>>("/api/searches?limit=100"),
        ])
        setFolders(foldersRes.items)
        setTags(tagsRes.items)
        setSearches(searchesRes.items)
      } catch {
        // If load failed and we haven't exceeded max retries, retry in 2 seconds
        if (retryCount < MAX_RETRIES) {
          retryCount++
          retryTimer = setTimeout(loadWithRetry, 2000)
        }
      }
    }

    loadWithRetry()

    return () => {
      if (retryTimer) clearTimeout(retryTimer)
      // Clean up any active summary streaming on unmount
      summaryControllerRef.current?.abort()
    }
  }, [])

  const refreshSearches = useCallback(async (silent = false): Promise<boolean> => {
    try {
      const res = await api.get<PaginatedResponse<SavedSearch>>("/api/searches?limit=100")
      setSearches(res.items)
      return true
    } catch (err) {
      if (!silent) {
        console.warn("Failed to load searches:", err)
      }
      return false
    }
  }, [])

  // Reset historical metadata
  const resetHistoricalState = useCallback(() => {
    setIsHistorical(false)
    setResultsChanged(false)
    setMissingFiles([])
    setNewFiles([])
    setScoreChanges([])
    setStoredResultCount(null)
    setCurrentResultCount(null)
    setCreatedAt(null)
    setVersionCount(0)
  }, [])

  const search = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true)
    setLoadingHistorical(false)
    setError(null)

    // Reset historical flags - this is a new search
    resetHistoricalState()

    // Stop any running summary
    summaryControllerRef.current?.abort()
    setSummary("")
    setSummarySources([])

    try {
      const res = await api.post<SearchResponse>("/api/search", {
        query: query.trim(),
        folder: folder || undefined,
        tag: tag || undefined,
        scope_ids: scopeIds || undefined,
        ad_hoc_tags: adHocTags && adHocTags.length > 0 ? adHocTags : undefined,
      })
      setResults(res.results)
      setActiveSearchId(res.search_id)
      refreshSearches()

      // Notify user if intelligent search fell back due to offline LLM
      if (res.llm_offline) {
        toast.warning("Intelligent search unavailable (LLM offline), using standard search")
      }

      // Start AI summary streaming
      setIsSummarizing(true)
      summaryControllerRef.current = streamSearchSummary(
        query.trim(),
        {
          onToken: (delta) => setSummary((prev) => prev + delta),
          onSources: (sources) => setSummarySources(sources),
          onDone: () => setIsSummarizing(false),
          onError: (err) => {
            setIsSummarizing(false)
            console.error("Summary error:", err)
          },
        },
        { folder, tag, search_id: res.search_id, scope_ids: scopeIds, ad_hoc_tags: adHocTags },
      )
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Search failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }, [query, folder, tag, scopeIds, adHocTags, refreshSearches, resetHistoricalState])

  const deleteSearch = useCallback(async (id: string) => {
    try {
      await api.del(`/api/searches/${id}`)
      setSearches((prev) => prev.filter((s) => s.id !== id))
      if (activeSearchId === id) setActiveSearchId(null)
    } catch (err) {
      console.warn("Failed to delete search:", err)
    }
  }, [activeSearchId])

  const loadSearch = useCallback(async (saved: SavedSearch) => {
    setQuery(saved.query)
    setFolder(saved.folder)
    setTag(saved.tag)
    setActiveSearchId(saved.id)

    // Stop any running summary
    summaryControllerRef.current?.abort()
    setIsSummarizing(false)

    setLoading(true)
    setLoadingHistorical(true)
    setError(null)
    resetHistoricalState()

    try {
      // Fast load: get stored results + metadata (no re-search)
      const res = await api.get<SearchResponse>(`/api/searches/${saved.id}/load`)

      setResults(res.results)
      setIsHistorical(res.is_historical)
      setCreatedAt(res.created_at || null)
      setVersionCount(res.version_count || 0)
      setSummary(res.summary || "")
      setSummarySources([])
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Failed to load search: ${msg}`)
    } finally {
      setLoading(false)
    }

    // Lazy compare: fetch change detection in background (slow, non-blocking)
    api.get<CompareResponse>(`/api/searches/${saved.id}/compare`).then((cmp) => {
      setResultsChanged(cmp.results_changed)
      setMissingFiles(cmp.missing_files)
      setNewFiles(cmp.new_files)
      setScoreChanges(cmp.score_changes)
      setStoredResultCount(cmp.stored_result_count)
      setCurrentResultCount(cmp.current_result_count)
    }).catch((err) => {
      console.warn("Results comparison failed:", err)
    })
  }, [resetHistoricalState])

  const loadVersion = useCallback(async (version: SearchVersion) => {
    // Load a specific version by creating a minimal SavedSearch object
    await loadSearch({
      id: version.id,
      query: version.query,
      folder: folder,
      tag: tag,
      summary: version.summary,
      result_paths: [],
      result_count: version.result_count,
      parent_id: version.parent_id,
      last_viewed_at: null,
      created_at: version.created_at,
    })
  }, [loadSearch, folder, tag])

  const fetchVersions = useCallback(async (searchId: string): Promise<SearchVersion[]> => {
    try {
      const res = await api.get<{ versions: SearchVersion[] }>(`/api/searches/${searchId}/versions`)
      return res.versions
    } catch (err) {
      console.warn("Failed to fetch search versions:", err)
      return []
    }
  }, [])

  const requery = useCallback(async () => {
    if (!query.trim()) return

    setLoading(true)
    setLoadingHistorical(false)
    setError(null)

    // Reset historical flags - this is a fresh search
    resetHistoricalState()

    // Stop any running summary
    summaryControllerRef.current?.abort()
    setSummary("")
    setSummarySources([])

    try {
      // Execute a new search linked to the current search (version chain)
      const res = await api.post<SearchResponse>("/api/search", {
        query: query.trim(),
        folder: folder || undefined,
        tag: tag || undefined,
        scope_ids: scopeIds || undefined,
        ad_hoc_tags: adHocTags && adHocTags.length > 0 ? adHocTags : undefined,
        parent_id: activeSearchId || undefined,
      })

      setResults(res.results)
      setActiveSearchId(res.search_id)
      refreshSearches()

      // Notify user if intelligent search fell back due to offline LLM
      if (res.llm_offline) {
        toast.warning("Intelligent search unavailable (LLM offline), using standard search")
      }

      // Generate fresh summary
      setIsSummarizing(true)
      summaryControllerRef.current = streamSearchSummary(
        query.trim(),
        {
          onToken: (delta) => setSummary((prev) => prev + delta),
          onSources: (sources) => setSummarySources(sources),
          onDone: () => setIsSummarizing(false),
          onError: (err) => {
            setIsSummarizing(false)
            console.error("Summary error:", err)
          },
        },
        { folder, tag, search_id: res.search_id, scope_ids: scopeIds, ad_hoc_tags: adHocTags },
      )
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Re-query failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }, [query, folder, tag, scopeIds, adHocTags, activeSearchId, refreshSearches, resetHistoricalState])

  const stopSummary = useCallback(() => {
    summaryControllerRef.current?.abort()
    setIsSummarizing(false)
  }, [])

  const generateSummary = useCallback(async () => {
    if (!query.trim()) return

    // Stop any running summary
    summaryControllerRef.current?.abort()
    setSummary("")
    setSummarySources([])

    // Start AI summary streaming
    setIsSummarizing(true)
    summaryControllerRef.current = streamSearchSummary(
      query.trim(),
      {
        onToken: (delta) => setSummary((prev) => prev + delta),
        onSources: (sources) => setSummarySources(sources),
        onDone: () => setIsSummarizing(false),
        onError: (err) => {
          setIsSummarizing(false)
          console.error("Summary error:", err)
          toast.error(`Failed to generate summary: ${err.message}`)
        },
      },
      { folder, tag, search_id: activeSearchId || undefined, scope_ids: scopeIds, ad_hoc_tags: adHocTags },
    )
  }, [query, folder, tag, activeSearchId, scopeIds, adHocTags])

  const newSearch = useCallback(() => {
    summaryControllerRef.current?.abort()
    setQuery("")
    setFolder(null)
    setTag(null)
    setResults([])
    setSummary("")
    setSummarySources([])
    setIsSummarizing(false)
    setActiveSearchId(null)
    setError(null)
    resetHistoricalState()
  }, [resetHistoricalState])

  return {
    query, setQuery, folder, setFolder, tag, setTag,
    results, folders, tags, loading, loadingHistorical, error, search,
    searches, activeSearchId, deleteSearch, loadSearch,
    summary, summarySources, isSummarizing, stopSummary, generateSummary,
    newSearch, refreshSearches, requery,
    loadVersion, fetchVersions,
    // Historical search metadata
    isHistorical, resultsChanged, missingFiles, newFiles, scoreChanges,
    storedResultCount, currentResultCount, createdAt, versionCount,
  }
}
