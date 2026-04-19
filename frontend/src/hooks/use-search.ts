import { useCallback, useEffect, useState } from "react"
import { api, retryWithBackoff } from "@/lib/api"
import { toast } from "sonner"
import { useSearchSummary, INITIAL_SUMMARY } from "./use-search-summary"
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

export function useSearch(scopeIds?: string | null, adHocTags?: string[] | null, bucketIds?: string | null) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingHistorical, setLoadingHistorical] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Search history
  const [searches, setSearches] = useState<SavedSearch[]>([])
  const [activeSearchId, setActiveSearchId] = useState<string | null>(null)

  // Historical search metadata (compound state)
  const [historical, setHistorical] = useState<HistoricalMeta>(INITIAL_HISTORICAL)

  // Deep research mode
  const [deepResearch, setDeepResearch] = useState(false)
  const [deepResearchIterations, setDeepResearchIterations] = useState(3)

  // AI summary (extracted hook)
  const {
    summary, summarySources, summaryStatus, isSummarizing,
    summaryIteration, summaryTotalIterations,
    summaryModel, summaryProvider,
    resetSummary, startSummary, stopSummary, abortSummary, setSummaryState,
  } = useSearchSummary(scopeIds, adHocTags, deepResearch, deepResearchIterations)

  useEffect(() => {
    const cancelRetry = retryWithBackoff(async () => {
      try {
        const searchesRes = await api.get<PaginatedResponse<SavedSearch>>("/api/v1/searches?limit=100")
        setSearches(searchesRes.items)
        return true
      } catch (err) {
        console.warn("Failed to load search panel data:", (err as Error).message)
        return false
      }
    })

    return () => {
      cancelRetry()
      abortSummary()
    }
  }, [abortSummary])

  const refreshSearches = useCallback(async (silent = false): Promise<boolean> => {
    try {
      const res = await api.get<PaginatedResponse<SavedSearch>>("/api/v1/searches?limit=100")
      setSearches(res.items)
      return true
    } catch (err) {
      if (!silent) {
        toast.error(`Failed to load searches: ${(err as Error).message}`)
      }
      return false
    }
  }, [])

  const executeSearch = useCallback(async (parentId?: string | null) => {
    if (!query.trim()) return
    setLoading(true)
    setLoadingHistorical(false)
    setError(null)
    setHistorical(INITIAL_HISTORICAL)
    resetSummary()

    try {
      const res = await api.post<SearchResponse>("/api/v1/search", {
        query: query.trim(),
        scope_ids: scopeIds || undefined,
        ad_hoc_tags: adHocTags && adHocTags.length > 0 ? adHocTags : undefined,
        bucket_ids: bucketIds || undefined,
        ...(parentId ? { parent_id: parentId } : {}),
      })
      setResults(res.results)
      setActiveSearchId(res.search_id)
      void refreshSearches()

      if (res.llm_offline) {
        toast.warning("Intelligent search unavailable (LLM offline), using standard search")
      }

      startSummary(query.trim(), { search_id: res.search_id })
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`${parentId ? "Re-query" : "Search"} failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }, [query, scopeIds, adHocTags, bucketIds, refreshSearches, resetSummary, startSummary])

  const search = useCallback(() => executeSearch(), [executeSearch])

  const requery = useCallback(() => executeSearch(activeSearchId), [executeSearch, activeSearchId])

  const renameSearch = useCallback(async (id: string, query: string) => {
    try {
      await api.patch(`/api/v1/searches/${id}`, { query })
      setSearches((prev) =>
        prev.map((s) => (s.id === id ? { ...s, query } : s)),
      )
    } catch (err) {
      toast.error(`Failed to rename search: ${(err as Error).message}`)
    }
  }, [])

  const deleteSearch = useCallback(async (id: string) => {
    try {
      await api.del(`/api/v1/searches/${id}`)
      setSearches((prev) => prev.filter((s) => s.id !== id))
      if (activeSearchId === id) setActiveSearchId(null)
    } catch (err) {
      toast.error(`Failed to delete search: ${(err as Error).message}`)
    }
  }, [activeSearchId])

  const loadSearch = useCallback(async (saved: SavedSearch) => {
    setQuery(saved.query)
    setActiveSearchId(saved.id)
    abortSummary()
    setSummaryState((s) => ({ ...s, isActive: false }))

    setLoading(true)
    setLoadingHistorical(true)
    setError(null)
    setHistorical(INITIAL_HISTORICAL)

    try {
      const res = await api.get<SearchResponse>(`/api/v1/searches/${saved.id}/load`)
      setResults(res.results)
      setHistorical(prev => ({
        ...prev,
        isHistorical: res.is_historical,
        createdAt: res.created_at || null,
        versionCount: res.version_count || 0,
      }))
      setSummaryState({ ...INITIAL_SUMMARY, text: res.summary || "" })
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Failed to load search: ${msg}`)
    } finally {
      setLoading(false)
    }

    // Lazy compare: fetch change detection in background
    api.get<CompareResponse>(`/api/v1/searches/${saved.id}/compare`).then((cmp) => {
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
  }, [abortSummary, setSummaryState])

  const loadVersion = useCallback(async (version: SearchVersion) => {
    await loadSearch({
      id: version.id,
      query: version.query,
      summary: version.summary,
      source: null,
      result_paths: [],
      result_count: version.result_count,
      parent_id: version.parent_id,
      last_viewed_at: null,
      created_at: version.created_at,
    })
  }, [loadSearch])

  const fetchVersions = useCallback(async (searchId: string): Promise<SearchVersion[]> => {
    try {
      const res = await api.get<{ versions: SearchVersion[] }>(`/api/v1/searches/${searchId}/versions`)
      return res.versions
    } catch (err) {
      console.warn("Failed to load search versions:", (err as Error).message)
      toast.error("Failed to load search versions")
      return []
    }
  }, [])

  const generateSummary = useCallback(async () => {
    if (!query.trim()) return
    resetSummary()
    startSummary(query.trim(), { search_id: activeSearchId || undefined })
  }, [query, activeSearchId, resetSummary, startSummary])

  const newSearch = useCallback(() => {
    abortSummary()
    setQuery("")
    setResults([])
    setSummaryState(INITIAL_SUMMARY)
    setActiveSearchId(null)
    setError(null)
    setHistorical(INITIAL_HISTORICAL)
  }, [abortSummary, setSummaryState])

  return {
    query, setQuery,
    results, loading, loadingHistorical, error, search,
    searches, activeSearchId, renameSearch, deleteSearch, loadSearch,
    summary, summarySources, summaryStatus, isSummarizing,
    summaryIteration, summaryTotalIterations,
    summaryModel, summaryProvider,
    stopSummary, generateSummary,
    deepResearch, setDeepResearch,
    deepResearchIterations, setDeepResearchIterations,
    newSearch, refreshSearches, requery,
    loadVersion, fetchVersions,
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
