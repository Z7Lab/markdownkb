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

  // Clean up poll on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  // On mount, release the checking-cache gate so the scope-aware fetch
  // effect in the consumer can run. Adoption of any in-progress build is
  // handled implicitly: fetchDocMap's own progress poll picks it up.
  // We deliberately do NOT fetch data here — this hook has no knowledge of
  // the active scope/tags/bucket, so a fetch here would pull the full
  // unscoped corpus and then immediately get aborted by the scoped fetch.
  useEffect(() => {
    setCheckingCache(false)
  }, [])

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
    // Tracks whether this invocation is still the live fetch. A superseded
    // call must not touch shared state (isLoading, progress, pollRef) or
    // it will clobber the newer call that replaced it.
    const isCurrent = () => abortRef.current === controller

    setIsLoading(true)
    setIsComputing(true)
    setProgress({ fraction: 0, phase: "Starting..." })

    try {
      const dataPromise = api.get<DocMapData>(`/api/docmap/data${buildDocmapQs(scopeIds, wc, adHocTags, bucketId)}`, controller.signal)
      await new Promise(r => setTimeout(r, 50))
      if (isCurrent()) {
        pollRef.current = setInterval(async () => {
          try {
            const p = await api.get<GraphProgress>("/api/docmap/progress")
            if (p.phase !== "idle" && isCurrent()) {
              setProgress(p)
            }
          } catch {
            // Ignore poll errors
          }
        }, 1000)
      }

      const data = await dataPromise
      if (!isCurrent() || controller.signal.aborted) return
      docmapDataRef.current = data
      setDocMapData(data)
      setFetchedAt(Date.now() / 1000)
      setSelectedNodeId(null)
      setSearchTerm("")
    } catch (err) {
      if (!isCurrent() || controller.signal.aborted) return
      const e = err as Error
      if (e.name === "AbortError") return
      toast.error(`Failed to load graph: ${e.message}`)
    } finally {
      if (isCurrent()) {
        if (pollRef.current) {
          clearInterval(pollRef.current)
          pollRef.current = null
        }
        setProgress({ fraction: 0, phase: "idle" })
        setIsComputing(false)
        setIsLoading(false)
      }
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
