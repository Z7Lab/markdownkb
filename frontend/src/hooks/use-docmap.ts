import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import type { DocMapData } from "@/lib/types"

interface GraphProgress {
  fraction: number
  phase: string
}

/** Server-side minimum edge weight — edges below this are never sent. */
export const DOCMAP_MIN_WEIGHT = 0.6

export function buildDocmapQs(scopeIds?: string | null, wordClouds = true, adHocTags?: string[] | null, bucketId?: string | null): string {
  const params = new URLSearchParams()
  if (scopeIds) params.set("scope_ids", scopeIds)
  if (!wordClouds) params.set("word_clouds", "false")
  params.set("min_weight", String(DOCMAP_MIN_WEIGHT))
  if (adHocTags && adHocTags.length > 0) {
    for (const t of adHocTags) params.append("ad_hoc_tags", t)
  }
  if (bucketId) params.set("bucket_id", bucketId)
  const qs = params.toString()
  return qs ? `?${qs}` : ""
}

export function useDocmap() {
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

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const docmapDataRef = useRef<DocMapData | null>(null)
  const lastScopeRef = useRef<string | null | undefined>(undefined)
  const lastTagsRef = useRef<string | null>(null)
  const lastBucketRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Ref to read latest wordClouds value inside the mount-only effect without
  // adding wordClouds to the dependency array (which would break mount-once semantics).
  const wordCloudsRef = useRef(wordClouds)
  useEffect(() => { wordCloudsRef.current = wordClouds }, [wordClouds])

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
        const mw = `&min_weight=${DOCMAP_MIN_WEIGHT}`
        const [withWc, withoutWc, prog] = await Promise.all([
          api.get<{ cached: boolean }>(`/api/docmap/status?word_clouds=true${mw}`, controller.signal),
          api.get<{ cached: boolean }>(`/api/docmap/status?word_clouds=false${mw}`, controller.signal),
          api.get<{ fraction: number; phase: string }>("/api/docmap/progress", controller.signal),
        ])
        if (controller.signal.aborted) return
        if (docmapDataRef.current) return

        const hasCached = withWc.cached || withoutWc.cached
        if (hasCached) {
          const useWc = withWc.cached
          setIsLoading(true)
          const data = await api.get<DocMapData>(`/api/docmap/data${buildDocmapQs(null, useWc)}`, controller.signal)
          if (controller.signal.aborted) return
          if (docmapDataRef.current) return
          docmapDataRef.current = data
          lastScopeRef.current = null
          setWordClouds(useWc)
          setDocMapData(data)
          setFetchedAt(Date.now() / 1000)
        } else if (prog.phase !== "idle") {
          setIsLoading(true)
          setIsComputing(true)
          setProgress(prog)
          pollRef.current = setInterval(async () => {
            try {
              const p = await api.get<{ fraction: number; phase: string }>("/api/docmap/progress")
              if (p.phase === "idle") {
                if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
                setProgress({ fraction: 0, phase: "idle" })
                setIsComputing(false)
                try {
                  const data = await api.get<DocMapData>(`/api/docmap/data${buildDocmapQs(null, wordCloudsRef.current)}`)
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
  }, []) // Mount-only: wordCloudsRef provides latest wordClouds without triggering re-runs

  const fetchDocMap = useCallback(async (
    scopeIds?: string | null,
    force = false,
    wc = true,
    adHocTags?: string[] | null,
    bucketId?: string | null,
  ) => {
    const tagsKey = adHocTags ? adHocTags.sort().join(",") : null
    const bucketKey = bucketId ?? null
    if (!force && docmapDataRef.current && lastScopeRef.current === scopeIds && lastTagsRef.current === tagsKey && lastBucketRef.current === bucketKey) {
      return
    }
    lastScopeRef.current = scopeIds ?? null
    lastTagsRef.current = tagsKey
    lastBucketRef.current = bucketKey

    abortRef.current?.abort()
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }

    const controller = new AbortController()
    abortRef.current = controller

    setIsLoading(true)
    setIsComputing(true)
    setProgress({ fraction: 0, phase: "Starting..." })

    try {
      const dataPromise = api.get<DocMapData>(`/api/docmap/data${buildDocmapQs(scopeIds, wc, adHocTags, bucketId)}`, controller.signal)
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
      if (controller.signal.aborted) return
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
  }
}
