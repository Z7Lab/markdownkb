import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import ForceGraph3D from "react-force-graph-3d"
import { useGraph } from "@/hooks/use-graph"
import { useScopes } from "@/hooks/use-scopes"
import { useIndexEvents } from "@/hooks/use-index-events"
import { GraphSidebar } from "./graph-sidebar"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { AlertTriangle, Loader2, MonitorX } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { GraphNode } from "@/lib/types"

function detectWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas")
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl")
    return gl instanceof WebGLRenderingContext || gl instanceof WebGL2RenderingContext
  } catch {
    return false
  }
}

// Cluster color palette — distinct hues
const CLUSTER_COLORS = [
  "#6366f1", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6",
  "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#14b8a6",
  "#a855f7", "#eab308", "#22c55e", "#e11d48", "#3b82f6",
]

const UNCLUSTERED_COLOR = "#6b7280"
const DIM_COLOR = "#1f2937"
const HIGHLIGHT_COLOR = "#facc15"

export function GraphTab() {
  const {
    graphData, isLoading, fetchedAt, threshold, setThreshold,
    selectedNodeId, selectNode, clearSelection,
    searchTerm, setSearchTerm, fetchGraph,
  } = useGraph()
  const { scopes, selectedScopeId, setSelectedScopeId } = useScopes()
  const { lastIndexedAt } = useIndexEvents()
  const [viewingPath, setViewingPath] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })
  const [webglSupported] = useState(() => detectWebGL())

  // Fetch on mount and scope change
  useEffect(() => {
    fetchGraph(selectedScopeId)
  }, [fetchGraph, selectedScopeId])

  // Track container dimensions
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      setDimensions({ width: Math.floor(width), height: Math.floor(height) })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  // Staleness
  const isStale = !!(lastIndexedAt && fetchedAt && lastIndexedAt > fetchedAt)

  // Build set of highlighted node IDs
  const highlightedNodes = useMemo(() => {
    if (!graphData) return new Set<string>()
    const set = new Set<string>()

    if (searchTerm) {
      const lower = searchTerm.toLowerCase()
      for (const node of graphData.nodes) {
        const inLabel = node.label.toLowerCase().includes(lower)
        const inTags = node.tags.some(t => t.toLowerCase().includes(lower))
        const inHeadings = node.headings.some(h => h.toLowerCase().includes(lower))
        const inWordCloud = Object.keys(node.word_cloud).some(t => t.toLowerCase().includes(lower))
        if (inLabel || inTags || inHeadings || inWordCloud) {
          set.add(node.id)
        }
      }
    } else if (selectedNodeId) {
      set.add(selectedNodeId)
      // Also highlight connected nodes
      for (const edge of graphData.edges) {
        if (edge.weight >= threshold) {
          if (edge.source === selectedNodeId) set.add(edge.target)
          if (edge.target === selectedNodeId) set.add(edge.source)
        }
      }
    }
    return set
  }, [graphData, searchTerm, selectedNodeId, threshold])

  const hasHighlight = highlightedNodes.size > 0

  // Filter edges by threshold, transform to force graph links format
  const forceGraphData = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] }
    return {
      nodes: graphData.nodes.map(n => ({ ...n })),
      links: graphData.edges
        .filter(e => e.weight >= threshold)
        .map(e => ({
          source: e.source,
          target: e.target,
          weight: e.weight,
        })),
    }
  }, [graphData, threshold])

  // Active word cloud based on selection state
  const { activeWordCloud, wordCloudLabel } = useMemo(() => {
    if (!graphData) return { activeWordCloud: {}, wordCloudLabel: "Terms" }

    if (selectedNodeId) {
      const node = graphData.nodes.find(n => n.id === selectedNodeId)
      if (node) {
        return {
          activeWordCloud: node.word_cloud,
          wordCloudLabel: `Terms: ${node.label}`,
        }
      }
    }

    if (searchTerm && highlightedNodes.size > 0) {
      // Merge word clouds from highlighted nodes
      const merged: Record<string, number> = {}
      for (const node of graphData.nodes) {
        if (highlightedNodes.has(node.id)) {
          for (const [term, w] of Object.entries(node.word_cloud)) {
            merged[term] = (merged[term] || 0) + w
          }
        }
      }
      return {
        activeWordCloud: merged,
        wordCloudLabel: `Terms: ${highlightedNodes.size} matched docs`,
      }
    }

    return {
      activeWordCloud: graphData.global_word_cloud,
      wordCloudLabel: "Terms: All documents",
    }
  }, [graphData, selectedNodeId, searchTerm, highlightedNodes])

  // Node color callback
  const nodeColor = useCallback((node: GraphNode) => {
    if (hasHighlight) {
      if (highlightedNodes.has(node.id)) {
        if (node.id === selectedNodeId) return HIGHLIGHT_COLOR
        return CLUSTER_COLORS[((node.cluster_id % CLUSTER_COLORS.length) + CLUSTER_COLORS.length) % CLUSTER_COLORS.length] || UNCLUSTERED_COLOR
      }
      return DIM_COLOR
    }
    if (node.cluster_id < 0) return UNCLUSTERED_COLOR
    return CLUSTER_COLORS[node.cluster_id % CLUSTER_COLORS.length] || UNCLUSTERED_COLOR
  }, [hasHighlight, highlightedNodes, selectedNodeId])

  // Node size: chunk count, enlarged when highlighted
  const nodeVal = useCallback((node: GraphNode) => {
    const base = Math.max(1, node.chunk_count)
    if (hasHighlight && highlightedNodes.has(node.id)) return base * 2
    return base
  }, [hasHighlight, highlightedNodes])

  // Node tooltip
  const nodeLabel = useCallback((node: GraphNode) => {
    const tags = node.tags.length > 0 ? `<br/>Tags: ${node.tags.join(", ")}` : ""
    return `<div style="max-width:300px"><strong>${node.label}</strong><br/>${node.chunk_count} chunks${tags}</div>`
  }, [])

  // Link styling
  const linkColor = useCallback((link: { source: string; target: string }) => {
    if (!hasHighlight) return "rgba(255,255,255,0.15)"
    const srcId = typeof link.source === "object" ? (link.source as any).id : link.source
    const tgtId = typeof link.target === "object" ? (link.target as any).id : link.target
    if (highlightedNodes.has(srcId) && highlightedNodes.has(tgtId)) {
      return "rgba(250,204,21,0.6)"
    }
    return "rgba(255,255,255,0.04)"
  }, [hasHighlight, highlightedNodes])

  const linkWidth = useCallback((link: { weight: number }) => {
    return Math.max(0.3, link.weight * 3)
  }, [])

  // Node click
  const handleNodeClick = useCallback((node: GraphNode) => {
    selectNode(node.id)
    setViewingPath(node.id)
  }, [selectNode])

  // Background click
  const handleBackgroundClick = useCallback(() => {
    clearSelection()
  }, [clearSelection])

  // Term click from word cloud
  const handleTermClick = useCallback((term: string) => {
    setSearchTerm(term)
    selectNode(null)
  }, [setSearchTerm, selectNode])

  const handleScopeChange = useCallback((id: string | null) => {
    setSelectedScopeId(id)
  }, [setSelectedScopeId])

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <GraphSidebar
        scopes={scopes}
        selectedScopeId={selectedScopeId}
        onScopeChange={handleScopeChange}
        threshold={threshold}
        onThresholdChange={setThreshold}
        searchTerm={searchTerm}
        onSearchChange={(term) => { setSearchTerm(term); selectNode(null) }}
        onRefresh={() => fetchGraph(selectedScopeId)}
        isLoading={isLoading}
        activeWordCloud={activeWordCloud}
        wordCloudLabel={wordCloudLabel}
        onTermClick={handleTermClick}
      />

      <div ref={containerRef} className="flex-1 min-w-0 min-h-0 relative bg-background">
        {/* Staleness indicator */}
        {isStale && (
          <div className="absolute top-3 right-3 z-10 flex items-center gap-2 bg-yellow-500/10 border border-yellow-500/30 rounded-md px-3 py-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-yellow-500" />
            <span className="text-xs text-yellow-500">Graph may be outdated</span>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs text-yellow-500"
              onClick={() => fetchGraph(selectedScopeId)}
            >
              Refresh
            </Button>
          </div>
        )}

        {/* Stats bar */}
        {graphData && !isLoading && (
          <div className="absolute top-3 left-3 z-10 text-xs text-muted-foreground bg-background/80 rounded px-2 py-1">
            {graphData.stats.doc_count} docs · {graphData.stats.chunk_count} chunks · {forceGraphData.links.length} edges
          </div>
        )}

        {/* Loading state */}
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center z-10 bg-background/50">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Computing graph...</span>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && graphData && graphData.nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <p className="text-sm">No documents found</p>
              <p className="text-xs mt-1">Index some documents first, or change the scope filter</p>
            </div>
          </div>
        )}

        {/* WebGL unavailable fallback */}
        {!webglSupported && graphData && graphData.nodes.length > 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-muted-foreground max-w-md space-y-3">
              <MonitorX className="h-10 w-10 mx-auto text-muted-foreground/60" />
              <p className="text-sm font-medium">WebGL is not available</p>
              <p className="text-xs leading-relaxed">
                The 3D knowledge graph requires WebGL, which needs hardware GPU access.
                This can happen with remote desktop sessions or systems without a GPU driver.
                Try accessing this page from a local browser session.
              </p>
              <p className="text-xs text-muted-foreground/60">
                {graphData.stats.doc_count} docs · {graphData.stats.chunk_count} chunks · {graphData.stats.edge_count} edges ready to visualize
              </p>
            </div>
          </div>
        )}

        {/* 3D Force Graph */}
        {webglSupported && graphData && graphData.nodes.length > 0 && (
          <ForceGraph3D
            graphData={forceGraphData}
            width={dimensions.width}
            height={dimensions.height}
            backgroundColor="#09090b"
            nodeId="id"
            nodeLabel={nodeLabel as any}
            nodeColor={nodeColor as any}
            nodeVal={nodeVal as any}
            nodeOpacity={0.9}
            nodeResolution={12}
            linkColor={linkColor as any}
            linkWidth={linkWidth as any}
            linkOpacity={0.6}
            onNodeClick={handleNodeClick as any}
            onBackgroundClick={handleBackgroundClick}
            showNavInfo={false}
            enableNodeDrag={true}
            cooldownTicks={100}
            warmupTicks={50}
          />
        )}
      </div>

      <FileViewerDialog
        path={viewingPath}
        onClose={() => setViewingPath(null)}
      />
    </div>
  )
}
