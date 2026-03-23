import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import ForceGraph3D from "react-force-graph-3d"
import { useGraph } from "@/hooks/use-graph"
import { useScopes } from "@/hooks/use-scopes"
import { useTags } from "@/hooks/use-tags"
import { useScopeTagFilter } from "@/hooks/use-scope-tag-filter"
import { useIndexEvents } from "@/hooks/use-index-events"
import { GraphSidebar } from "./graph-sidebar"
import { EdgeDetailPanel } from "./edge-detail-panel"
import { GraphControls } from "./graph-controls"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { AlertTriangle, Loader2, MonitorX } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { ForceGraphRef, GraphNode } from "@/lib/types"
import { dirname } from "@/lib/utils"

function detectWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas")
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl")
    return gl instanceof WebGLRenderingContext || gl instanceof WebGL2RenderingContext
  } catch {
    return false
  }
}

/** Observe .dark class on <html> to track theme changes */
function useIsDark() {
  const [isDark, setIsDark] = useState(
    () => document.documentElement.classList.contains("dark"),
  )
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains("dark"))
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] })
    return () => observer.disconnect()
  }, [])
  return isDark
}

// Cluster color palette — uses CSS-compatible values that complement Tailwind's default palette
const CLUSTER_COLORS = [
  "oklch(0.585 0.233 277)",  // indigo-500
  "oklch(0.769 0.188 70.1)", // amber-500
  "oklch(0.765 0.177 163)",  // emerald-500
  "oklch(0.637 0.237 25.3)", // red-500
  "oklch(0.606 0.25 292)",   // violet-500
  "oklch(0.715 0.143 215)",  // cyan-500
  "oklch(0.702 0.183 55.1)", // orange-500
  "oklch(0.768 0.233 130)",  // lime-500
  "oklch(0.656 0.241 354)",  // pink-500
  "oklch(0.704 0.14 182)",   // teal-500
  "oklch(0.627 0.265 303)",  // purple-500
  "oklch(0.795 0.184 86.1)", // yellow-500
  "oklch(0.723 0.219 149)",  // green-500
  "oklch(0.598 0.25 360)",   // rose-600
  "oklch(0.623 0.214 259)",  // blue-500
]

const UNCLUSTERED_COLOR = "oklch(0.551 0.027 264)" // gray-500
const HIGHLIGHT_COLOR = "oklch(0.852 0.199 91.9)"  // yellow-300

// Theme-aware colors — these must remain raw values for WebGL canvas rendering
const THEME = {
  dark: { bg: "#09090b", dim: "#1f2937", linkBase: "140,180,255", linkDim: "255,255,255" },
  light: { bg: "#f8fafc", dim: "#d1d5db", linkBase: "59,130,246", linkDim: "0,0,0" },
} as const

/** Force-graph link with weight metadata */
interface GraphLink {
  source: string | { id: string }
  target: string | { id: string }
  weight: number
}

/** Extract node ID from a link endpoint (handles both string and object forms) */
function linkNodeId(endpoint: string | { id: string }): string {
  return typeof endpoint === "object" ? endpoint.id : endpoint
}

/** Hook for container dimension tracking via ResizeObserver */
function useContainerDimensions() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })

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

  return { containerRef, dimensions }
}

export function GraphTab() {
  const {
    graphData, isLoading, isComputing, checkingCache, fetchedAt, threshold, setThreshold,
    wordClouds, setWordClouds,
    selectedNodeId, selectNode, clearSelection,
    searchTerm, setSearchTerm, fetchGraph, progress,
  } = useGraph()
  const { scopes } = useScopes()
  const { tags: availableTags } = useTags()
  const { lastIndexedAt } = useIndexEvents()
  const isDark = useIsDark()
  const colors = isDark ? THEME.dark : THEME.light
  const [viewingPath, setViewingPath] = useState<string | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<{ source: string; target: string; weight: number } | null>(null)
  const { containerRef, dimensions } = useContainerDimensions()
  const fgRef = useRef<ForceGraphRef | null>(null)
  const [webglSupported] = useState(() => detectWebGL())
  const [spread, setSpread] = useState(100)
  const spreadInitialized = useRef(false)
  const initialFitDone = useRef(false)

  const {
    selectedScopeIds, selectedTags,
    scopeIdsParam, adHocTagsParam,
    handleScopeChange, handleTagChange,
  } = useScopeTagFilter()

  const prevScopeRef = useRef(scopeIdsParam)
  const prevTagsRef = useRef(adHocTagsParam)

  // Re-fetch when scope or tag selection changes (not on initial mount)
  useEffect(() => {
    const scopeChanged = prevScopeRef.current !== scopeIdsParam
    const tagsChanged = JSON.stringify(prevTagsRef.current) !== JSON.stringify(adHocTagsParam)
    if (scopeChanged || tagsChanged) {
      prevScopeRef.current = scopeIdsParam
      prevTagsRef.current = adHocTagsParam
      fetchGraph(scopeIdsParam, true, wordClouds, adHocTagsParam)
    }
  }, [fetchGraph, scopeIdsParam, adHocTagsParam, wordClouds])

  // Staleness
  const isStale = !!(lastIndexedAt && fetchedAt && lastIndexedAt > fetchedAt)

  // Build set of highlighted node IDs
  const highlightedNodes = useMemo(() => {
    if (!graphData) return new Set<string>()
    const set = new Set<string>()

    if (searchTerm) {
      const terms = searchTerm.toLowerCase().split(/\s+/).filter(Boolean)
      if (terms.length > 0) {
        for (const node of graphData.nodes) {
          const label = node.label.toLowerCase()
          const tags = node.tags.map(t => t.toLowerCase())
          const headings = node.headings.map(h => h.toLowerCase())
          const wcKeys = Object.keys(node.word_cloud).map(t => t.toLowerCase())
          const matchesAll = terms.every(term =>
            label.includes(term)
            || tags.some(t => t.includes(term))
            || headings.some(h => h.includes(term))
            || wcKeys.some(k => k.includes(term)),
          )
          if (matchesAll) set.add(node.id)
        }
      }
    } else if (selectedNodeId) {
      set.add(selectedNodeId)
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

  // Filter edges by threshold and remove disconnected nodes
  const forceGraphData = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] }
    const links = graphData.edges
      .filter(e => e.weight >= threshold)
      .map(e => ({
        source: e.source,
        target: e.target,
        weight: e.weight,
      }))
    const connectedIds = new Set<string>()
    for (const link of links) {
      connectedIds.add(link.source)
      connectedIds.add(link.target)
    }
    return {
      nodes: graphData.nodes
        .filter(n => connectedIds.has(n.id))
        .map(n => ({ ...n })),
      links,
    }
  }, [graphData, threshold])

  // Configure d3 forces — spread slider scales all distances
  useEffect(() => {
    const fg = fgRef.current
    if (!fg) return
    const s = spread / 100
    const charge = fg.d3Force("charge")
    if (charge) {
      charge.strength(-1500 * s)
      charge.distanceMax(2000 * s)
    }
    const link = fg.d3Force("link")
    if (link) {
      link.distance((l: GraphLink) => {
        const w = typeof l.weight === "number" ? l.weight : 0.5
        return (200 + (1 - w) * 800) * s
      })
      link.strength((l: GraphLink) => {
        const w = typeof l.weight === "number" ? l.weight : 0.5
        return w * 0.15
      })
    }
    const center = fg.d3Force("center")
    if (center) {
      center.strength(0.02)
    }
    if (spreadInitialized.current) {
      fg.d3ReheatSimulation()
    } else {
      spreadInitialized.current = true
    }
  }, [forceGraphData, spread])

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
      return colors.dim
    }
    if (node.cluster_id < 0) return UNCLUSTERED_COLOR
    return CLUSTER_COLORS[node.cluster_id % CLUSTER_COLORS.length] || UNCLUSTERED_COLOR
  }, [hasHighlight, highlightedNodes, selectedNodeId, colors.dim])

  // Node size: chunk count, enlarged when highlighted
  const nodeVal = useCallback((node: GraphNode) => {
    const base = Math.max(1, node.chunk_count)
    if (hasHighlight && highlightedNodes.has(node.id)) return base * 2
    return base
  }, [hasHighlight, highlightedNodes])

  // Node tooltip — escape user-controlled values to prevent XSS
  const nodeLabel = useCallback((node: GraphNode) => {
    const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;")
    const dir = dirname(node.id)
    const tags = node.tags.length > 0 ? `<br/>Tags: ${esc(node.tags.join(", "))}` : ""
    return `<div style="max-width:350px"><strong>${esc(node.label)}</strong><br/><span style="opacity:0.7">${esc(dir)}</span><br/>${node.chunk_count} chunks${tags}</div>`
  }, [])

  // Link styling
  const linkColor = useCallback((link: GraphLink) => {
    if (hasHighlight) {
      const srcId = linkNodeId(link.source)
      const tgtId = linkNodeId(link.target)
      if (highlightedNodes.has(srcId) && highlightedNodes.has(tgtId)) {
        return "rgba(250,204,21,0.8)"
      }
      return `rgba(${colors.linkDim},0.03)`
    }
    const w = typeof link.weight === "number" ? link.weight : 0.5
    const alpha = Math.min(0.6, 0.08 + w * 0.5)
    return `rgba(${colors.linkBase},${alpha.toFixed(2)})`
  }, [hasHighlight, highlightedNodes, colors])

  const linkWidth = useCallback((link: GraphLink) => {
    const w = typeof link.weight === "number" ? link.weight : 0.5
    return Math.max(0.5, w * w * 8)
  }, [])

  // Node click
  const handleNodeClick = useCallback((node: GraphNode) => {
    selectNode(node.id)
    setViewingPath(node.id)
    setSelectedEdge(null)
  }, [selectNode])

  // Link click — show edge detail
  const handleLinkClick = useCallback((link: GraphLink) => {
    const srcId = linkNodeId(link.source)
    const tgtId = linkNodeId(link.target)
    setSelectedEdge({ source: srcId, target: tgtId, weight: link.weight ?? 0 })
  }, [])

  // Background click / clear all selection
  const handleBackgroundClick = useCallback(() => {
    clearSelection()
    setSelectedEdge(null)
    setSearchTerm("")
  }, [clearSelection, setSearchTerm])

  // Term click from word cloud
  const handleTermClick = useCallback((term: string) => {
    setSearchTerm(term)
    selectNode(null)
  }, [setSearchTerm, selectNode])

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <GraphSidebar
        scopes={scopes}
        selectedScopeIds={selectedScopeIds}
        onScopeChange={handleScopeChange}
        availableTags={availableTags}
        selectedTags={selectedTags}
        onTagChange={handleTagChange}
        threshold={threshold}
        onThresholdChange={setThreshold}
        spread={spread}
        onSpreadChange={setSpread}
        searchTerm={searchTerm}
        onSearchChange={(term) => { setSearchTerm(term); selectNode(null) }}
        onRefresh={() => fetchGraph(scopeIdsParam, true, wordClouds, adHocTagsParam)}
        isLoading={isLoading}
        wordCloudsEnabled={wordClouds}
        onWordCloudsChange={setWordClouds}
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
              onClick={() => fetchGraph(scopeIdsParam, true, wordClouds, adHocTagsParam)}
            >
              Refresh
            </Button>
          </div>
        )}

        {/* Stats bar */}
        {graphData && !isLoading && (
          <div className="absolute top-3 left-3 z-10 text-xs text-muted-foreground bg-background/80 rounded px-2 py-1">
            {forceGraphData.nodes.length}/{graphData.stats.doc_count} docs · {forceGraphData.links.length} edges
          </div>
        )}

        {/* Loading state with progress */}
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center z-10 bg-background/50">
            <div className="flex flex-col items-center gap-3 text-muted-foreground w-64">
              <div className="flex items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>{isComputing ? "Computing graph..." : "Loading graph..."}</span>
              </div>
              {isComputing && progress.phase !== "idle" && (
                <>
                  <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-primary h-full rounded-full transition-all duration-300"
                      style={{ width: `${Math.round(progress.fraction * 100)}%` }}
                    />
                  </div>
                  <span className="text-xs">{progress.phase}</span>
                </>
              )}
            </div>
          </div>
        )}

        {/* Not yet built */}
        {!isLoading && !checkingCache && !graphData && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-muted-foreground space-y-3">
              <p className="text-sm font-medium">Knowledge graph not built yet</p>
              <p className="text-xs">Build the graph to visualize document relationships</p>
              <Button variant="outline" size="sm" onClick={() => fetchGraph(scopeIdsParam, true, wordClouds, adHocTagsParam)}>
                Build Graph
              </Button>
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

        {/* 3D Force Graph — react-force-graph-3d uses NodeObject/LinkObject generics
            that don't structurally match our domain types. A single cast on the
            component props is cleaner than per-prop `as never`. */}
        {webglSupported && graphData && graphData.nodes.length > 0 && (
          <ForceGraph3D
            ref={fgRef as never}
            graphData={forceGraphData}
            width={dimensions.width}
            height={dimensions.height}
            backgroundColor={colors.bg}
            nodeId="id"
            {...{
              nodeLabel,
              nodeColor,
              nodeVal,
              linkColor,
              linkWidth,
              onNodeClick: handleNodeClick,
              onLinkClick: handleLinkClick,
            } as Record<string, unknown>}
            nodeOpacity={0.9}
            nodeResolution={12}
            linkOpacity={0.6}
            linkDirectionalParticles={0}
            onBackgroundClick={handleBackgroundClick}
            showNavInfo={false}
            enableNodeDrag={true}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            cooldownTicks={200}
            warmupTicks={100}
            onEngineStop={() => {
              if (!initialFitDone.current) {
                initialFitDone.current = true
                fgRef.current?.zoomToFit(400, 60)
              }
            }}
          />
        )}

        {/* Zoom controls */}
        {webglSupported && graphData && graphData.nodes.length > 0 && !isLoading && (
          <GraphControls
            fgRef={fgRef}
            hasSelection={!!selectedNodeId || !!selectedEdge || !!searchTerm}
            onClearSelection={handleBackgroundClick}
          />
        )}

        {/* Edge detail panel */}
        {selectedEdge && (
          <EdgeDetailPanel
            source={selectedEdge.source}
            target={selectedEdge.target}
            weight={selectedEdge.weight}
            onClose={() => setSelectedEdge(null)}
            onDocClick={(path) => setViewingPath(path)}
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
