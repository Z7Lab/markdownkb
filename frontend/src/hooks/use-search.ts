import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { streamSearchSummary } from "@/lib/sse"
import { toast } from "sonner"
import type { PaginatedResponse, SavedSearch, SearchResult, SearchResponse, ScoreChange } from "@/lib/types"

export function useSearch() {
  const [query, setQuery] = useState("")
  const [folder, setFolder] = useState<string | null>(null)
  const [tag, setTag] = useState<string | null>(null)
  const [results, setResults] = useState<SearchResult[]>([])
  const [folders, setFolders] = useState<string[]>([])
  const [tags, setTags] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Search history
  const [searches, setSearches] = useState<SavedSearch[]>([])
  const [activeSearchId, setActiveSearchId] = useState<string | null>(null)

  // Historical search metadata
  const [isHistorical, setIsHistorical] = useState(false)
  const [currentView, setCurrentView] = useState<"original" | "current">("original")
  const [resultsChanged, setResultsChanged] = useState(false)
  const [missingFiles, setMissingFiles] = useState<string[]>([])
  const [newFiles, setNewFiles] = useState<string[]>([])
  const [scoreChanges, setScoreChanges] = useState<ScoreChange[]>([])
  const [storedResultCount, setStoredResultCount] = useState<number | null>(null)
  const [currentResultCount, setCurrentResultCount] = useState<number | null>(null)
  const [createdAt, setCreatedAt] = useState<string | null>(null)

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
    setCurrentView("original")
    setResultsChanged(false)
    setMissingFiles([])
    setNewFiles([])
    setScoreChanges([])
    setStoredResultCount(null)
    setCurrentResultCount(null)
    setCreatedAt(null)
  }, [])

  const search = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true)
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
        { folder, tag, search_id: res.search_id },
      )
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Search failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }, [query, folder, tag, refreshSearches, resetHistoricalState])

  const deleteSearch = useCallback(async (id: string) => {
    try {
      await api.del(`/api/searches/${id}`)
      setSearches((prev) => prev.filter((s) => s.id !== id))
      if (activeSearchId === id) setActiveSearchId(null)
    } catch { /* ignore */ }
  }, [activeSearchId])

  const loadSearch = useCallback(async (saved: SavedSearch, view: "original" | "current" = "original") => {
    setQuery(saved.query)
    setFolder(saved.folder)
    setTag(saved.tag)
    setActiveSearchId(saved.id)
    setCurrentView(view)

    // Stop any running summary
    summaryControllerRef.current?.abort()
    setIsSummarizing(false)

    setLoading(true)
    setError(null)

    try {
      // Call the load endpoint to get historical search data with view parameter
      const res = await api.get<SearchResponse>(`/api/searches/${saved.id}/load?view=${view}`)

      // Set results
      setResults(res.results)

      // Set historical metadata
      setIsHistorical(res.is_historical)
      setResultsChanged(res.results_changed || false)
      setMissingFiles(res.missing_files || [])
      setNewFiles(res.new_files || [])
      setScoreChanges(res.score_changes || [])
      setStoredResultCount(res.stored_result_count || null)
      setCurrentResultCount(res.current_result_count || null)
      setCreatedAt(res.created_at || null)

      // Use the stored summary (don't regenerate)
      setSummary(res.summary || "")
      setSummarySources([]) // Sources aren't stored in historical searches
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Failed to load search: ${msg}`)
    } finally {
      setLoading(false)
    }
  }, [])

  const requery = useCallback(async () => {
    if (!query.trim()) return

    setLoading(true)
    setError(null)

    // Reset historical flags - this is a fresh search
    resetHistoricalState()

    // Stop any running summary
    summaryControllerRef.current?.abort()
    setSummary("")
    setSummarySources([])

    try {
      // Execute a new search (creates new search record)
      const res = await api.post<SearchResponse>("/api/search", {
        query: query.trim(),
        folder: folder || undefined,
        tag: tag || undefined,
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
        { folder, tag, search_id: res.search_id },
      )
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Re-query failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }, [query, folder, tag, refreshSearches, resetHistoricalState])

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
      { folder, tag, search_id: activeSearchId || undefined },
    )
  }, [query, folder, tag, activeSearchId])

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

  const toggleView = useCallback(async () => {
    if (!isHistorical || !activeSearchId) return

    const newView = currentView === "original" ? "current" : "original"
    setCurrentView(newView)
    setLoading(true)
    setError(null)

    try {
      // Reload with the new view
      const res = await api.get<SearchResponse>(`/api/searches/${activeSearchId}/load?view=${newView}`)
      setResults(res.results)

      // Update metadata (comparison data remains same, but results change)
      setResultsChanged(res.results_changed || false)
      setMissingFiles(res.missing_files || [])
      setNewFiles(res.new_files || [])
      setScoreChanges(res.score_changes || [])
      setStoredResultCount(res.stored_result_count || null)
      setCurrentResultCount(res.current_result_count || null)
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Failed to toggle view: ${msg}`)
    } finally {
      setLoading(false)
    }
  }, [isHistorical, activeSearchId, currentView])

  return {
    query, setQuery, folder, setFolder, tag, setTag,
    results, folders, tags, loading, error, search,
    searches, activeSearchId, deleteSearch, loadSearch,
    summary, summarySources, isSummarizing, stopSummary, generateSummary,
    newSearch, refreshSearches, requery, toggleView,
    // Historical search metadata
    isHistorical, currentView, resultsChanged, missingFiles, newFiles, scoreChanges,
    storedResultCount, currentResultCount, createdAt,
  }
}
