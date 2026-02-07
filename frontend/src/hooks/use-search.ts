import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { streamSearchSummary } from "@/lib/sse"
import { toast } from "sonner"
import type { PaginatedResponse, SavedSearch, SearchResult } from "@/lib/types"

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

  const search = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)

    // Stop any running summary
    summaryControllerRef.current?.abort()
    setSummary("")
    setSummarySources([])

    try {
      const res = await api.post<{ results: SearchResult[]; search_id: string; llm_offline?: boolean }>("/api/search", {
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
  }, [query, folder, tag, refreshSearches])

  const deleteSearch = useCallback(async (id: string) => {
    try {
      await api.del(`/api/searches/${id}`)
      setSearches((prev) => prev.filter((s) => s.id !== id))
      if (activeSearchId === id) setActiveSearchId(null)
    } catch { /* ignore */ }
  }, [activeSearchId])

  // Helper to execute search (DRY)
  const executeSearch = useCallback(async (
    query: string,
    folder: string | null,
    tag: string | null,
  ): Promise<{ results: SearchResult[]; search_id: string } | null> => {
    setLoading(true)
    try {
      const res = await api.post<{ results: SearchResult[]; search_id: string }>("/api/search", {
        query,
        folder: folder || undefined,
        tag: tag || undefined,
      })
      setResults(res.results)
      return res
    } catch (err) {
      console.error("Failed to execute search:", err)
      setError((err as Error).message)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const loadSearch = useCallback(async (saved: SavedSearch) => {
    setQuery(saved.query)
    setFolder(saved.folder)
    setTag(saved.tag)
    setActiveSearchId(saved.id)

    // Stop any running summary
    summaryControllerRef.current?.abort()
    setIsSummarizing(false)

    // If we have a cached summary, use it and just refresh results
    if (saved.summary) {
      setSummary(saved.summary)
      setSummarySources([]) // Sources aren't saved, so clear them

      // Refresh results in background (results may have changed with new indexing)
      await executeSearch(saved.query, saved.folder, saved.tag)
      // Note: This creates a new search record, but we keep showing the old summary
    } else {
      // No cached summary - fetch results and generate summary
      setSummary("")
      setSummarySources([])

      const res = await executeSearch(saved.query, saved.folder, saved.tag)
      if (!res) return

      // Generate summary and save to the OLD search record (not the new one)
      setIsSummarizing(true)
      summaryControllerRef.current = streamSearchSummary(
        saved.query,
        {
          onToken: (delta) => setSummary((prev) => prev + delta),
          onSources: (sources) => setSummarySources(sources),
          onDone: () => setIsSummarizing(false),
          onError: (err) => {
            setIsSummarizing(false)
            console.error("Summary error:", err)
          },
        },
        { folder: saved.folder, tag: saved.tag, search_id: saved.id },
      )
    }
  }, [executeSearch])

  const stopSummary = useCallback(() => {
    summaryControllerRef.current?.abort()
    setIsSummarizing(false)
  }, [])

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
  }, [])

  return {
    query, setQuery, folder, setFolder, tag, setTag,
    results, folders, tags, loading, error, search,
    searches, activeSearchId, deleteSearch, loadSearch,
    summary, summarySources, isSummarizing, stopSummary,
    newSearch, refreshSearches,
  }
}
