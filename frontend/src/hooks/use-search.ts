import { useCallback, useEffect, useRef, useState } from "react"
import { api, retryWithBackoff } from "@/lib/api"
import { streamSearchSummary } from "@/lib/sse"
import { toast } from "sonner"
import type { PaginatedResponse, SavedSearch, SearchResult, SearchResponse, CompareResponse, SearchVersion, ScoreChange } from "@/lib/types"

/** Historical search comparison metadata — always set/reset together */
interface HistoricalMeta {
  isHistorical: boolean
  resultsChanged: boolean
  missingFiles: string[]
  newFiles: string[]
  scoreChanges: ScoreChange[]
  storedResultCount: number | null
  currentResultCount: number | null
  createdAt: string | null
  versionCount: number
}

const INITIAL_HISTORICAL: HistoricalMeta = {
  isHistorical: false,
  resultsChanged: false,
  missingFiles: [],
  newFiles: [],
  scoreChanges: [],
  storedResultCount: null,
  currentResultCount: null,
  createdAt: null,
  versionCount: 0,
}

export function useSearch(scopeIds?: string | null, adHocTags?: string[] | null, bucketId?: string | null) {
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

  // Historical search metadata (compound state)
  const [historical, setHistorical] = useState<HistoricalMeta>(INITIAL_HISTORICAL)

  // AI summary
  const [summary, setSummary] = useState("")
  const [summarySources, setSummarySources] = useState<string[]>([])
  const [isSummarizing, setIsSummarizing] = useState(false)
  const [summaryStatus, setSummaryStatus] = useState<string | null>(null)
  const summaryControllerRef = useRef<AbortController | null>(null)

  // Deep research mode
  const [deepResearch, setDeepResearch] = useState(false)
  const [deepResearchIterations, setDeepResearchIterations] = useState(3)
  const [summaryIteration, setSummaryIteration] = useState(0)
  const [summaryTotalIterations, setSummaryTotalIterations] = useState(0)

  // API key is set once before mount via setApiKey() and does not change at runtime,
  // so an empty dependency array is correct here — no re-fetch needed on key change.
  useEffect(() => {
    const cancelRetry = retryWithBackoff(async () => {
      try {
        const [foldersRes, tagsRes, searchesRes] = await Promise.all([
          api.get<PaginatedResponse<string>>("/api/folders"),
          api.get<PaginatedResponse<string>>("/api/tags"),
          api.get<PaginatedResponse<SavedSearch>>("/api/searches?limit=100"),
        ])
        setFolders(foldersRes.items)
        setTags(tagsRes.items)
        setSearches(searchesRes.items)
        return true
      } catch (err) {
        console.warn("Failed to load search panel data:", (err as Error).message)
        return false
      }
    })

    return () => {
      cancelRetry()
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
        toast.error(`Failed to load searches: ${(err as Error).message}`)
      }
      return false
    }
  }, [])

  /** Stop any running summary and reset summary state */
  const resetSummary = useCallback(() => {
    summaryControllerRef.current?.abort()
    setSummary("")
    setSummarySources([])
    setSummaryStatus(null)
    setSummaryIteration(0)
    setSummaryTotalIterations(0)
  }, [])

  /** Start streaming an AI summary for the given query */
  const startSummary = useCallback((
    searchQuery: string,
    options: { folder?: string | null; tag?: string | null; search_id?: string | null },
  ) => {
    setIsSummarizing(true)
    setSummaryStatus(null)
    setSummaryIteration(0)
    setSummaryTotalIterations(0)
    summaryControllerRef.current = streamSearchSummary(
      searchQuery,
      {
        onToken: (delta) => {
          setSummaryStatus(null)
          setSummary((prev) => prev + delta)
        },
        onSources: (sources) => setSummarySources(sources),
        onStatus: (_phase, message, iteration, totalIterations) => {
          setSummaryStatus(message)
          if (iteration !== undefined) setSummaryIteration(iteration)
          if (totalIterations !== undefined) setSummaryTotalIterations(totalIterations)
        },
        onDone: () => {
          setIsSummarizing(false)
          setSummaryStatus(null)
        },
        onError: (err) => {
          setIsSummarizing(false)
          setSummaryStatus(null)
          toast.error(`Summary failed: ${err.message}`)
        },
      },
      {
        ...options,
        scope_ids: scopeIds,
        ad_hoc_tags: adHocTags,
        deep_research: deepResearch,
        deep_research_iterations: deepResearch ? deepResearchIterations : undefined,
      },
    )
  }, [scopeIds, adHocTags, deepResearch, deepResearchIterations])

  /**
   * Shared logic for search and requery — executes a search POST and starts summary streaming.
   * The only difference is requery passes parent_id for version chaining.
   */
  const executeSearch = useCallback(async (parentId?: string | null) => {
    if (!query.trim()) return
    setLoading(true)
    setLoadingHistorical(false)
    setError(null)
    setHistorical(INITIAL_HISTORICAL)
    resetSummary()

    try {
      const res = await api.post<SearchResponse>("/api/search", {
        query: query.trim(),
        folder: folder || undefined,
        tag: tag || undefined,
        scope_ids: scopeIds || undefined,
        ad_hoc_tags: adHocTags && adHocTags.length > 0 ? adHocTags : undefined,
        bucket_id: bucketId || undefined,
        ...(parentId ? { parent_id: parentId } : {}),
      })
      setResults(res.results)
      setActiveSearchId(res.search_id)
      refreshSearches()

      if (res.llm_offline) {
        toast.warning("Intelligent search unavailable (LLM offline), using standard search")
      }

      startSummary(query.trim(), { folder, tag, search_id: res.search_id })
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`${parentId ? "Re-query" : "Search"} failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }, [query, folder, tag, scopeIds, adHocTags, bucketId, refreshSearches, resetSummary, startSummary])

  const search = useCallback(() => executeSearch(), [executeSearch])

  const requery = useCallback(() => executeSearch(activeSearchId), [executeSearch, activeSearchId])

  const renameSearch = useCallback(async (id: string, query: string) => {
    try {
      await api.patch(`/api/searches/${id}`, { query })
      setSearches((prev) =>
        prev.map((s) => (s.id === id ? { ...s, query } : s)),
      )
    } catch (err) {
      toast.error(`Failed to rename search: ${(err as Error).message}`)
    }
  }, [])

  const deleteSearch = useCallback(async (id: string) => {
    try {
      await api.del(`/api/searches/${id}`)
      setSearches((prev) => prev.filter((s) => s.id !== id))
      if (activeSearchId === id) setActiveSearchId(null)
    } catch (err) {
      toast.error(`Failed to delete search: ${(err as Error).message}`)
    }
  }, [activeSearchId])

  const loadSearch = useCallback(async (saved: SavedSearch) => {
    setQuery(saved.query)
    setFolder(saved.folder)
    setTag(saved.tag)
    setActiveSearchId(saved.id)

    summaryControllerRef.current?.abort()
    setIsSummarizing(false)

    setLoading(true)
    setLoadingHistorical(true)
    setError(null)
    setHistorical(INITIAL_HISTORICAL)

    try {
      const res = await api.get<SearchResponse>(`/api/searches/${saved.id}/load`)
      setResults(res.results)
      setHistorical(prev => ({
        ...prev,
        isHistorical: res.is_historical,
        createdAt: res.created_at || null,
        versionCount: res.version_count || 0,
      }))
      setSummary(res.summary || "")
      setSummarySources([])
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Failed to load search: ${msg}`)
    } finally {
      setLoading(false)
    }

    // Lazy compare: fetch change detection in background
    api.get<CompareResponse>(`/api/searches/${saved.id}/compare`).then((cmp) => {
      setHistorical(prev => ({
        ...prev,
        resultsChanged: cmp.results_changed,
        missingFiles: cmp.missing_files,
        newFiles: cmp.new_files,
        scoreChanges: cmp.score_changes,
        storedResultCount: cmp.stored_result_count,
        currentResultCount: cmp.current_result_count,
      }))
    }).catch(() => {
      /* comparison is best-effort background check */
    })
  }, [])

  const loadVersion = useCallback(async (version: SearchVersion) => {
    await loadSearch({
      id: version.id,
      query: version.query,
      folder: folder,
      tag: tag,
      summary: version.summary,
      source: null,
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
      console.warn("Failed to load search versions:", (err as Error).message)
      toast.error("Failed to load search versions")
      return []
    }
  }, [])

  const stopSummary = useCallback(() => {
    summaryControllerRef.current?.abort()
    setIsSummarizing(false)
    setSummaryStatus(null)
    setSummaryIteration(0)
    setSummaryTotalIterations(0)
  }, [])

  const generateSummary = useCallback(async () => {
    if (!query.trim()) return
    resetSummary()
    startSummary(query.trim(), { folder, tag, search_id: activeSearchId || undefined })
  }, [query, folder, tag, activeSearchId, resetSummary, startSummary])

  const newSearch = useCallback(() => {
    summaryControllerRef.current?.abort()
    setQuery("")
    setFolder(null)
    setTag(null)
    setResults([])
    setSummary("")
    setSummarySources([])
    setIsSummarizing(false)
    setSummaryStatus(null)
    setSummaryIteration(0)
    setSummaryTotalIterations(0)
    setActiveSearchId(null)
    setError(null)
    setHistorical(INITIAL_HISTORICAL)
  }, [])

  return {
    query, setQuery, folder, setFolder, tag, setTag,
    results, folders, tags, loading, loadingHistorical, error, search,
    searches, activeSearchId, renameSearch, deleteSearch, loadSearch,
    summary, summarySources, summaryStatus, isSummarizing, stopSummary, generateSummary,
    deepResearch, setDeepResearch,
    deepResearchIterations, setDeepResearchIterations,
    summaryIteration, summaryTotalIterations,
    newSearch, refreshSearches, requery,
    loadVersion, fetchVersions,
    // Historical search metadata (spread compound state for API compatibility)
    isHistorical: historical.isHistorical,
    resultsChanged: historical.resultsChanged,
    missingFiles: historical.missingFiles,
    newFiles: historical.newFiles,
    scoreChanges: historical.scoreChanges,
    storedResultCount: historical.storedResultCount,
    currentResultCount: historical.currentResultCount,
    createdAt: historical.createdAt,
    versionCount: historical.versionCount,
  }
}
