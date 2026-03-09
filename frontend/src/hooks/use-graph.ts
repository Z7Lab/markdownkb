import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import type { GraphData } from "@/lib/types"

interface GraphProgress {
  fraction: number
  phase: string
}

export function useGraph() {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [fetchedAt, setFetchedAt] = useState<number | null>(null)
  const [threshold, setThreshold] = useState(0.65)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState("")
  const [progress, setProgress] = useState<GraphProgress>({ fraction: 0, phase: "idle" })
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Clean up poll on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const fetchGraph = useCallback(async (scopeId?: string | null) => {
    setIsLoading(true)
    setProgress({ fraction: 0, phase: "Starting..." })

    // Poll progress while waiting
    pollRef.current = setInterval(async () => {
      try {
        const p = await api.get<GraphProgress>("/api/graph/progress")
        if (p.phase !== "idle") {
          setProgress(p)
        }
      } catch {
        // Ignore poll errors
      }
    }, 500)

    try {
      const params = new URLSearchParams()
      if (scopeId) params.set("scope_id", scopeId)
      const qs = params.toString()
      const data = await api.get<GraphData>(`/api/graph/data${qs ? `?${qs}` : ""}`)
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
    fetchedAt,
    threshold,
    setThreshold,
    selectedNodeId,
    selectNode,
    clearSelection,
    searchTerm,
    setSearchTerm,
    fetchGraph,
    progress,
  }
}
