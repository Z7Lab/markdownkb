import { useState } from "react"
import { useDocmap } from "./use-docmap"
import { useKnowledgeGraph } from "./use-knowledge-graph"

export type GraphMode = "similarity" | "knowledge"

export interface ExtractionStatus {
  running: boolean
  progress: number
  message: string
  result: string
  files_done: number
  files_total: number
}

/**
 * Combines document map and knowledge graph state into a single hook
 * consumed by VisualizationTab. See use-docmap.ts and use-knowledge-graph.ts
 * for domain-specific logic.
 */
export function useVisualization() {
  const [mode, setMode] = useState<GraphMode>("similarity")

  const docmap = useDocmap()
  const kg = useKnowledgeGraph(mode)

  return {
    // Docmap
    docmapData: docmap.docmapData,
    docmapStatus: docmap.status,
    fetchedAt: docmap.fetchedAt,
    threshold: docmap.threshold,
    setThreshold: docmap.setThreshold,
    wordClouds: docmap.wordClouds,
    setWordClouds: docmap.setWordClouds,
    bucketThreshold: docmap.bucketThreshold,
    setBucketThreshold: docmap.setBucketThreshold,
    selectedNodeId: docmap.selectedNodeId,
    selectNode: docmap.selectNode,
    clearSelection: docmap.clearSelection,
    searchTerm: docmap.searchTerm,
    setSearchTerm: docmap.setSearchTerm,
    fetchDocMap: docmap.fetchDocMap,
    progress: docmap.progress,
    // Mode (shared)
    mode,
    setMode,
    // Knowledge graph
    kgData: kg.kgData,
    kgLoading: kg.kgLoading,
    fetchKG: kg.fetchKG,
    extraction: kg.extraction,
    startExtraction: kg.startExtraction,
    cancelExtraction: kg.cancelExtraction,
  }
}
