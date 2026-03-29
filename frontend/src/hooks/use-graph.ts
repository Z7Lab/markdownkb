import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import type { GraphData } from "@/lib/types"

interface GraphProgress {
  fraction: number
  phase: string
}

/** Server-side minimum edge weight — edges below this are never sent. */
const MIN_WEIGHT = 0.6

function buildQs(scopeIds?: string | null, wordClouds = true, adHocTags?: string[] | null): string {
  const params = new URLSearchParams()
  if (scopeIds) params.set("scope_ids", scopeIds)
  if (!wordClouds) params.set("word_clouds", "false")
  params.set("min_weight", String(MIN_WEIGHT))
  if (adHocTags && adHocTags.length > 0) {
    for (const t of adHocTags) params.append("ad_hoc_tags", t)
  }
  const qs = params.toString()
  return qs ? `?${qs}` : ""
}

export function useGraph() {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isComputing, setIsComputing] = useState(false)
  const [checkingCache, setCheckingCache] = useState(true)
  const [fetchedAt, setFetchedAt] = useState<number | null>(null)
  const [threshold, setThreshold] = useState(0.75)
  const [wordClouds, setWordClouds] = useState(true)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState("")
  const [progress, setProgress] = useState<GraphProgress>({ fraction: 0, phase: "idle" })
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const graphDataRef = useRef<GraphData | null>(null)
  const lastScopeRef = useRef<string | null | undefined>(undefined)
  const abortRef = useRef<AbortController | null>(null)

  // Clean up poll on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  // On mount, check if server has cached graph data and load it transparently
  useEffect(() => {
    const controller = new AbortController()
    abortRef.current = controller
    ;(async () => {
      try {
        // Check both with and without word clouds
        const mw = `&min_weight=${MIN_WEIGHT}`
        const [withWc, withoutWc] = await Promise.all([
          api.get<{ cached: boolean }>(`/api/graph/status?word_clouds=true${mw}`, controller.signal),
          api.get<{ cached: boolean }>(`/api/graph/status?word_clouds=false${mw}`, controller.signal),
        ])
        if (controller.signal.aborted || graphDataRef.current) return

        const hasCached = withWc.cached || withoutWc.cached
        if (hasCached) {
          // Prefer the one that's cached; if both, prefer with word clouds
          const useWc = withWc.cached
          setIsLoading(true)
          const data = await api.get<GraphData>(`/api/graph/data${buildQs(null, useWc)}`, controller.signal)
          if (controller.signal.aborted) return
          graphDataRef.current = data
          lastScopeRef.current = null
          setWordClouds(useWc)
          setGraphData(data)
          setFetchedAt(Date.now() / 1000)
        }
      } catch {
        // Ignore — user can manually build (or request was aborted by fetchGraph)
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false)
          setCheckingCache(false)
        }
      }
    })()
    return () => { controller.abort() }
  }, [])

  const fetchGraph = useCallback(async (
    scopeIds?: string | null,
    force = false,
    wc = true,
    adHocTags?: string[] | null,
  ) => {
    // Skip if we already have data for this scope selection (unless forced)
    if (!force && graphDataRef.current && lastScopeRef.current === scopeIds) return
    lastScopeRef.current = scopeIds ?? null

    // Abort any in-flight cache check or previous fetch
    abortRef.current?.abort()
    abortRef.current = null
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }

    setIsLoading(true)
    setIsComputing(true)
    setProgress({ fraction: 0, phase: "Starting..." })

    try {
      // Start the data fetch first, then begin progress polling
      const dataPromise = api.get<GraphData>(`/api/graph/data${buildQs(scopeIds, wc, adHocTags)}`)

      // Brief delay so the data request claims a connection before polls compete
      await new Promise(r => setTimeout(r, 50))
      pollRef.current = setInterval(async () => {
        try {
          const p = await api.get<GraphProgress>("/api/graph/progress")
          if (p.phase !== "idle") {
            setProgress(p)
          }
        } catch {
          // Ignore poll errors
        }
      }, 1000)

      const data = await dataPromise
      graphDataRef.current = data
      setGraphData(data)
      setFetchedAt(Date.now() / 1000)
      setSelectedNodeId(null)
      setSearchTerm("")
    } catch (err) {
      toast.error(`Failed to load graph: ${(err as Error).message}`)
    } finally {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      setProgress({ fraction: 0, phase: "idle" })
      setIsComputing(false)
      setIsLoading(false)
    }
  }, [])

  const selectNode = useCallback((id: string | null) => {
    setSelectedNodeId(id)
    if (id) setSearchTerm("")
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedNodeId(null)
    setSearchTerm("")
  }, [])

  return {
    graphData,
    isLoading,
    isComputing,
    checkingCache,
    fetchedAt,
    threshold,
    setThreshold,
    wordClouds,
    setWordClouds,
    selectedNodeId,
    selectNode,
    clearSelection,
    searchTerm,
    setSearchTerm,
    fetchGraph,
    progress,
  }
}
