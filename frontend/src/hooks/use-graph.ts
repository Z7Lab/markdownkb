import { useCallback, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import type { GraphData } from "@/lib/types"

export function useGraph() {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [fetchedAt, setFetchedAt] = useState<number | null>(null)
  const [threshold, setThreshold] = useState(0.3)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState("")

  const fetchGraph = useCallback(async (scopeId?: string | null) => {
    setIsLoading(true)
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
  }
}
