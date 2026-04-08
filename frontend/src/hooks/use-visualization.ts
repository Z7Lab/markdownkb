import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import type { DocMapData, KGData } from "@/lib/types"

export type GraphMode = "similarity" | "knowledge"

interface GraphProgress {
  fraction: number
  phase: string
}

/** Server-side minimum edge weight — edges below this are never sent. */
const MIN_WEIGHT = 0.6

function buildQs(scopeIds?: string | null, wordClouds = true, adHocTags?: string[] | null, bucketId?: string | null): string {
  const params = new URLSearchParams()
  if (scopeIds) params.set("scope_ids", scopeIds)
  if (!wordClouds) params.set("word_clouds", "false")
  params.set("min_weight", String(MIN_WEIGHT))
  if (adHocTags && adHocTags.length > 0) {
    for (const t of adHocTags) params.append("ad_hoc_tags", t)
  }
  if (bucketId) params.set("bucket_id", bucketId)
  const qs = params.toString()
  return qs ? `?${qs}` : ""
}

export function useVisualization() {
  const [docmapData, setDocMapData] = useState<DocMapData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isComputing, setIsComputing] = useState(false)
  const [checkingCache, setCheckingCache] = useState(true)
  const [fetchedAt, setFetchedAt] = useState<number | null>(null)
  const [threshold, setThreshold] = useState(0.75)
  const [wordClouds, setWordClouds] = useState(true)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState("")
  const [progress, setProgress] = useState<GraphProgress>({ fraction: 0, phase: "idle" })
  const [mode, setMode] = useState<GraphMode>("similarity")
  const [kgData, setKgData] = useState<KGData | null>(null)
  const [kgLoading, setKgLoading] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const docmapDataRef = useRef<DocMapData | null>(null)
  const lastScopeRef = useRef<string | null | undefined>(undefined)
  const abortRef = useRef<AbortController | null>(null)

  // Clean up poll on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  // On mount, check for cached data or in-progress build
  useEffect(() => {
    const controller = new AbortController()
    abortRef.current = controller
    ;(async () => {
      try {
        // Check cache and build progress in parallel
        const mw = `&min_weight=${MIN_WEIGHT}`
        const [withWc, withoutWc, prog] = await Promise.all([
          api.get<{ cached: boolean }>(`/api/docmap/status?word_clouds=true${mw}`, controller.signal),
          api.get<{ cached: boolean }>(`/api/docmap/status?word_clouds=false${mw}`, controller.signal),
          api.get<{ fraction: number; phase: string }>("/api/docmap/progress", controller.signal),
        ])
        if (controller.signal.aborted || docmapDataRef.current) return

        const hasCached = withWc.cached || withoutWc.cached
        if (hasCached) {
          const useWc = withWc.cached
          setIsLoading(true)
          const data = await api.get<DocMapData>(`/api/docmap/data${buildQs(null, useWc)}`, controller.signal)
          if (controller.signal.aborted) return
          docmapDataRef.current = data
          lastScopeRef.current = null
          setWordClouds(useWc)
          setDocMapData(data)
          setFetchedAt(Date.now() / 1000)
        } else if (prog.phase !== "idle") {
          // A build is in progress from a previous tab visit — resume polling
          setIsLoading(true)
          setIsComputing(true)
          setProgress(prog)
          pollRef.current = setInterval(async () => {
            try {
              const p = await api.get<{ fraction: number; phase: string }>("/api/docmap/progress")
              if (p.phase === "idle") {
                // Build finished — fetch the cached result
                if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
                setProgress({ fraction: 0, phase: "idle" })
                setIsComputing(false)
                try {
                  const data = await api.get<DocMapData>(`/api/docmap/data${buildQs(null, wordClouds)}`)
                  docmapDataRef.current = data
                  lastScopeRef.current = null
                  setDocMapData(data)
                  setFetchedAt(Date.now() / 1000)
                } finally {
                  setIsLoading(false)
                }
              } else {
                setProgress(p)
              }
            } catch {
              // ignore poll errors
            }
          }, 1000)
        }
      } catch {
        // Ignore — user can manually build (or request was aborted)
      } finally {
        if (!controller.signal.aborted && !pollRef.current) {
          setIsLoading(false)
          setCheckingCache(false)
        }
      }
    })()
    return () => { controller.abort() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const lastTagsRef = useRef<string | null>(null)
  const lastBucketRef = useRef<string | null>(null)

  const fetchDocMap = useCallback(async (
    scopeIds?: string | null,
    force = false,
    wc = true,
    adHocTags?: string[] | null,
    bucketId?: string | null,
  ) => {
    // Skip if we already have data for this exact scope+tag+bucket selection (unless forced)
    const tagsKey = adHocTags ? adHocTags.sort().join(",") : null
    const bucketKey = bucketId ?? null
    if (!force && docmapDataRef.current && lastScopeRef.current === scopeIds && lastTagsRef.current === tagsKey && lastBucketRef.current === bucketKey) return
    lastScopeRef.current = scopeIds ?? null
    lastTagsRef.current = tagsKey
    lastBucketRef.current = bucketKey

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
      const dataPromise = api.get<DocMapData>(`/api/docmap/data${buildQs(scopeIds, wc, adHocTags, bucketId)}`)

      // Brief delay so the data request claims a connection before polls compete
      await new Promise(r => setTimeout(r, 50))
      pollRef.current = setInterval(async () => {
        try {
          const p = await api.get<GraphProgress>("/api/docmap/progress")
          if (p.phase !== "idle") {
            setProgress(p)
          }
        } catch {
          // Ignore poll errors
        }
      }, 1000)

      const data = await dataPromise
      docmapDataRef.current = data
      setDocMapData(data)
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

  const fetchKG = useCallback(async (entityTypes?: string, relTypes?: string) => {
    setKgLoading(true)
    try {
      const params = new URLSearchParams()
      if (entityTypes) params.set("entity_types", entityTypes)
      if (relTypes) params.set("rel_types", relTypes)
      const qs = params.toString()
      const data = await api.get<KGData>(`/api/knowledge-graph/data${qs ? `?${qs}` : ""}`)
      setKgData(data)
    } catch (err) {
      toast.error(`Failed to load knowledge graph: ${(err as Error).message}`)
    } finally {
      setKgLoading(false)
    }
  }, [])

  // Auto-fetch KG data when switching to knowledge mode
  useEffect(() => {
    if (mode === "knowledge" && !kgData && !kgLoading) {
      fetchKG()
    }
  }, [mode, kgData, kgLoading, fetchKG])

  // -- KG Extraction --
  interface ExtractionStatus {
    running: boolean
    progress: number
    message: string
    result: string
    files_done: number
    files_total: number
  }

  const [extraction, setExtraction] = useState<ExtractionStatus>({
    running: false, progress: 0, message: "", result: "", files_done: 0, files_total: 0,
  })
  const extractionPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const pollExtraction = useCallback(() => {
    if (extractionPollRef.current) clearInterval(extractionPollRef.current)
    extractionPollRef.current = setInterval(async () => {
      try {
        const s = await api.get<ExtractionStatus>("/api/knowledge-graph/extract/status")
        setExtraction(s)
        if (!s.running) {
          if (extractionPollRef.current) clearInterval(extractionPollRef.current)
          extractionPollRef.current = null
          // Refresh KG data after extraction completes
          fetchKG()
        }
      } catch {
        // ignore poll errors
      }
    }, 2000)
  }, [fetchKG])

  // Clean up poll on unmount
  useEffect(() => {
    return () => {
      if (extractionPollRef.current) clearInterval(extractionPollRef.current)
    }
  }, [])

  // Check extraction status on mode switch
  useEffect(() => {
    if (mode === "knowledge") {
      api.get<ExtractionStatus>("/api/knowledge-graph/extract/status")
        .then((s) => {
          setExtraction(s)
          if (s.running) pollExtraction()
        })
        .catch(() => {})
    }
  }, [mode, pollExtraction])

  const startExtraction = useCallback(async () => {
    try {
      await api.post("/api/knowledge-graph/extract")
      setExtraction((e) => ({ ...e, running: true, progress: 0, message: "Starting...", result: "" }))
      pollExtraction()
    } catch (err) {
      toast.error(`Failed to start extraction: ${(err as Error).message}`)
    }
  }, [pollExtraction])

  const cancelExtraction = useCallback(async () => {
    try {
      await api.post("/api/knowledge-graph/extract/cancel")
    } catch {
      // ignore
    }
  }, [])

  return {
    docmapData,
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
    fetchDocMap,
    progress,
    mode,
    setMode,
    kgData,
    kgLoading,
    fetchKG,
    extraction,
    startExtraction,
    cancelExtraction,
  }
}
