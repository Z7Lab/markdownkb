import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { setVisibilityInterval } from "@/lib/polling"
import { toast } from "sonner"
import type { KGData } from "@/lib/types"
import type { GraphMode, ExtractionStatus } from "./use-visualization"

export function useKnowledgeGraph(mode: GraphMode) {
  const [kgData, setKgData] = useState<KGData | null>(null)
  const [kgLoading, setKgLoading] = useState(false)
  const [extraction, setExtraction] = useState<ExtractionStatus>({
    running: false,
    progress: 0,
    message: "",
    result: "",
    files_done: 0,
    files_total: 0,
  })
  const extractionPollCleanupRef = useRef<(() => void) | null>(null)

  const fetchKG = useCallback(async (entityTypes?: string, relTypes?: string) => {
    setKgLoading(true)
    try {
      const params = new URLSearchParams()
      if (entityTypes) params.set("entity_types", entityTypes)
      if (relTypes) params.set("rel_types", relTypes)
      const qs = params.toString()
      const data = await api.get<KGData>(`/api/v1/knowledge-graph/data${qs ? `?${qs}` : ""}`)
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

  const pollExtraction = useCallback(() => {
    if (extractionPollCleanupRef.current) extractionPollCleanupRef.current()
    extractionPollCleanupRef.current = setVisibilityInterval(async () => {
      try {
        const s = await api.get<ExtractionStatus>("/api/v1/knowledge-graph/extract/status")
        setExtraction(s)
        if (!s.running) {
          if (extractionPollCleanupRef.current) extractionPollCleanupRef.current()
          extractionPollCleanupRef.current = null
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
      if (extractionPollCleanupRef.current) extractionPollCleanupRef.current()
    }
  }, [])

  // Check extraction status on mode switch
  useEffect(() => {
    if (mode === "knowledge") {
      api
        .get<ExtractionStatus>("/api/v1/knowledge-graph/extract/status")
        .then((s) => {
          setExtraction(s)
          if (s.running) pollExtraction()
        })
        .catch((e) => {
          console.warn("Knowledge graph: failed to check extraction status", e)
        })
    }
  }, [mode, pollExtraction])

  const startExtraction = useCallback(async () => {
    try {
      await api.post("/api/v1/knowledge-graph/extract")
      setExtraction((e) => ({ ...e, running: true, progress: 0, message: "Starting...", result: "" }))
      pollExtraction()
    } catch (err) {
      toast.error(`Failed to start extraction: ${(err as Error).message}`)
    }
  }, [pollExtraction])

  const cancelExtraction = useCallback(async () => {
    try {
      await api.post("/api/v1/knowledge-graph/extract/cancel")
    } catch {
      // ignore
    }
  }, [])

  return {
    kgData,
    kgLoading,
    fetchKG,
    extraction,
    startExtraction,
    cancelExtraction,
  }
}
