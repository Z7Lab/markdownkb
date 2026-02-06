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
    api.get<PaginatedResponse<string>>("/api/folders").then((r) => setFolders(r.items)).catch(() => {})
    api.get<PaginatedResponse<string>>("/api/tags").then((r) => setTags(r.items)).catch(() => {})
    refreshSearches()
  }, [])

  const refreshSearches = useCallback(async () => {
    try {
      const res = await api.get<PaginatedResponse<SavedSearch>>("/api/searches?limit=100")
      setSearches(res.items)
    } catch { /* ignore */ }
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
      const res = await api.post<{ results: SearchResult[]; search_id: string }>("/api/search", {
        query: query.trim(),
        folder: folder || undefined,
        tag: tag || undefined,
      })
      setResults(res.results)
      setActiveSearchId(res.search_id)
      refreshSearches()

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
        { folder, tag },
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

  const loadSearch = useCallback((saved: SavedSearch) => {
    setQuery(saved.query)
    setFolder(saved.folder)
    setTag(saved.tag)
    setActiveSearchId(saved.id)
  }, [])

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
