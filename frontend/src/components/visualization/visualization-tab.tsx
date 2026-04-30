import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useVisualization } from "@/hooks/use-visualization"
import { useScopes } from "@/hooks/use-scopes"
import { useTags } from "@/hooks/use-tags"
import { useScopeTagFilter } from "@/hooks/use-scope-tag-filter"
import { useBuckets } from "@/hooks/use-buckets"
import { useIndexEvents } from "@/hooks/use-index-events"
import { useIsDark } from "@/hooks/use-is-dark"
import { useContainerDimensions } from "@/hooks/use-container-dimensions"
import { TypedForceGraph3D } from "./typed-force-graph"
import type { GraphLink } from "./typed-force-graph"
import { VisualizationSidebar } from "./visualization-sidebar"
import { EdgeDetailPanel } from "./edge-detail-panel"
import { VisualizationControls } from "./visualization-controls"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { AlertTriangle, Loader2, MonitorX } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { ForceGraphRef, DocMapNode } from "@/lib/types"
import { dirname } from "@/lib/utils"

function detectWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas")
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl")
    return gl instanceof WebGLRenderingContext || gl instanceof WebGL2RenderingContext
  } catch (err) {
    console.error("WebGL detection failed unexpectedly:", err)
    return false
  }
}

// Cluster color palette — uses CSS-compatible values that complement Tailwind's default palette
const CLUSTER_COLORS = [
  "oklch(0.585 0.233 277)", // indigo-500
  "oklch(0.769 0.188 70.1)", // amber-500
  "oklch(0.765 0.177 163)", // emerald-500
  "oklch(0.637 0.237 25.3)", // red-500
  "oklch(0.606 0.25 292)", // violet-500
  "oklch(0.715 0.143 215)", // cyan-500
  "oklch(0.702 0.183 55.1)", // orange-500
  "oklch(0.768 0.233 130)", // lime-500
  "oklch(0.656 0.241 354)", // pink-500
  "oklch(0.704 0.14 182)", // teal-500
  "oklch(0.627 0.265 303)", // purple-500
  "oklch(0.795 0.184 86.1)", // yellow-500
  "oklch(0.723 0.219 149)", // green-500
  "oklch(0.598 0.25 360)", // rose-600
  "oklch(0.623 0.214 259)", // blue-500
]

const UNCLUSTERED_COLOR = "oklch(0.551 0.027 264)" // gray-500

// Entity type to color mapping for KG mode
const ENTITY_TYPE_COLORS: Record<string, string> = {
  concept: "oklch(0.585 0.233 277)", // indigo
  technology: "oklch(0.715 0.143 215)", // cyan
  tool: "oklch(0.765 0.177 163)", // emerald
  process: "oklch(0.769 0.188 70.1)", // amber
  pattern: "oklch(0.606 0.25 292)", // violet
  standard: "oklch(0.702 0.183 55.1)", // orange
  organization: "oklch(0.637 0.237 25.3)", // red
  person: "oklch(0.768 0.233 130)", // lime
  metric: "oklch(0.704 0.14 182)", // teal
  principle: "oklch(0.656 0.241 354)", // pink
}
const HIGHLIGHT_COLOR = "oklch(0.852 0.199 91.9)" // yellow-300
const BUCKET_COLOR = "#ff3333" // bright red — must be visible against all cluster colors

import { GRAPH_THEME } from "@/lib/constants"

/** Extract node ID from a link endpoint (handles both string and object forms) */
function linkNodeId(endpoint: string | { id: string }): string {
  return typeof endpoint === "object" ? endpoint.id : endpoint
}

import type { GraphMode } from "@/hooks/use-visualization"

export function VisualizationTab({ fixedMode }: { fixedMode: GraphMode }) {
  const {
    docmapData,
    docmapStatus,
    fetchedAt,
    threshold,
    setThreshold,
    wordClouds,
    setWordClouds,
    bucketThreshold,
    setBucketThreshold,
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
  } = useVisualization()

  // Lock mode to what the parent tab specifies
  useEffect(() => {
    setMode(fixedMode)
  }, [fixedMode, setMode])

  const { scopes } = useScopes()
  const { tags: availableTags } = useTags()
  const { lastIndexedAt } = useIndexEvents()
  const isDark = useIsDark()
  const colors = isDark ? GRAPH_THEME.dark : GRAPH_THEME.light
  const [viewingPath, setViewingPath] = useState<string | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<{ source: string; target: string; weight: number } | null>(null)
  const { containerRef, dimensions } = useContainerDimensions()
  const fgRef = useRef<ForceGraphRef | null>(null)
  const [webglSupported] = useState(() => detectWebGL())
  const [spread, setSpread] = useState(100)
  const spreadInitialized = useRef(false)
  const initialFitDone = useRef(false)
  const pendingRecenter = useRef(false)

  const {
    selectedScopeIds,
    selectedTags,
    scopeIdsParam,
    adHocTagsParam,
    selectedBucketIds,
    bucketIdsParam,
    handleScopeChange,
    handleTagChange,
    handleBucketChange,
  } = useScopeTagFilter()
  const { buckets } = useBuckets()
  const selectedBucketIdsArray = selectedBucketIds.size > 0 ? Array.from(selectedBucketIds) : null

  // Sentinel initial values so the first effect run always dispatches a
  // scope-aware fetch — otherwise the mount render would see refs === params
  // and skip, leaving the hook with no data at the user's actual scope.
  const prevScopeRef = useRef<string | null | undefined>(undefined)
  const prevTagsRef = useRef<string[] | null | undefined>(undefined)
  const prevWordCloudsRef = useRef<boolean | undefined>(undefined)
  const prevBucketRef = useRef<string | null | undefined>(undefined)
  const prevBucketThresholdRef = useRef<number | undefined>(undefined)

  // Fetch on mount with the user's active scope, and re-fetch when any
  // filter input changes. Bucket-threshold-only changes are debounced so
  // that dragging the slider doesn't fire a storm of concurrent builds —
  // the backend's RRF compute is ~1s per build and each in-flight request
  // holds memory for TF-IDF + pairwise sims, so 4 concurrent builds can
  // quadruple container memory usage.
  useEffect(() => {
    const scopeChanged = prevScopeRef.current !== scopeIdsParam
    const tagsChanged = JSON.stringify(prevTagsRef.current) !== JSON.stringify(adHocTagsParam)
    const wcChanged = prevWordCloudsRef.current !== wordClouds
    const bucketChanged = prevBucketRef.current !== bucketIdsParam
    const bucketThreshChanged = prevBucketThresholdRef.current !== bucketThreshold && !!selectedBucketIdsArray
    if (!scopeChanged && !tagsChanged && !wcChanged && !bucketChanged && !bucketThreshChanged) {
      return
    }
    const onlyThresholdChanged = bucketThreshChanged && !scopeChanged && !tagsChanged && !wcChanged && !bucketChanged
    const delay = onlyThresholdChanged ? 300 : 0
    const timer = setTimeout(() => {
      prevScopeRef.current = scopeIdsParam
      prevTagsRef.current = adHocTagsParam
      prevWordCloudsRef.current = wordClouds
      prevBucketRef.current = bucketIdsParam
      prevBucketThresholdRef.current = bucketThreshold
      fetchDocMap(
        scopeIdsParam,
        wcChanged || bucketChanged || bucketThreshChanged,
        wordClouds,
        adHocTagsParam,
        selectedBucketIdsArray,
        bucketThreshold,
      )
    }, delay)
    return () => clearTimeout(timer)
  }, [fetchDocMap, scopeIdsParam, adHocTagsParam, wordClouds, bucketIdsParam, selectedBucketIdsArray, bucketThreshold])

  // Staleness
  const isStale = !!(lastIndexedAt && fetchedAt && lastIndexedAt > fetchedAt)

  // Build set of highlighted node IDs
  const highlightedNodes = useMemo(() => {
    if (!docmapData) return new Set<string>()
    const set = new Set<string>()

    if (searchTerm) {
      const terms = searchTerm.toLowerCase().split(/\s+/).filter(Boolean)
      if (terms.length > 0) {
        for (const node of docmapData.nodes) {
          const label = node.label.toLowerCase()
          const tags = node.tags.map((t) => t.toLowerCase())
          const headings = node.headings.map((h) => h.toLowerCase())
          const wcKeys = Object.keys(node.word_cloud).map((t) => t.toLowerCase())
          const matchesAll = terms.every(
            (term) =>
              label.includes(term) ||
              tags.some((t) => t.includes(term)) ||
              headings.some((h) => h.includes(term)) ||
              wcKeys.some((k) => k.includes(term)),
          )
          if (matchesAll) set.add(node.id)
        }
      }
    } else if (selectedNodeId) {
      set.add(selectedNodeId)
      for (const edge of docmapData.edges) {
        if (edge.weight >= threshold) {
          if (edge.source === selectedNodeId) set.add(edge.target)
          if (edge.target === selectedNodeId) set.add(edge.source)
        }
      }
    }
    return set
  }, [docmapData, searchTerm, selectedNodeId, threshold])

  const hasHighlight = highlightedNodes.size > 0

  // Filter edges by threshold and remove disconnected nodes
  const forceDocMapData = useMemo(() => {
    if (!docmapData) return { nodes: [], links: [] }
    const nodeIds = new Set(docmapData.nodes.map((n) => n.id))
    // Bucket-involving edges already passed the server min_weight floor and
    // the per-bucket-doc top-N cap. The user's similarity threshold governs
    // intra-scope clarity — applying it to bucket edges silently nullifies
    // the Bucket Connections slider whenever cross-edge weights happen to
    // sit below the threshold (which is typical for thematic overlap).
    const bucketIds = new Set(docmapData.nodes.filter((n) => n._bucket).map((n) => n.id))
    const isBucketEdge = (e: { source: string; target: string }) => bucketIds.has(e.source) || bucketIds.has(e.target)
    const links = docmapData.edges
      .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target) && (isBucketEdge(e) || e.weight >= threshold))
      .map((e) => ({
        source: e.source,
        target: e.target,
        weight: e.weight,
      }))
    const connectedIds = new Set<string>()
    for (const link of links) {
      connectedIds.add(link.source)
      connectedIds.add(link.target)
    }
    // Always keep bucket nodes so isolated bucket docs render as floating
    // colored markers — the whole point of bucket selection is visibility.
    const result = {
      nodes: docmapData.nodes.filter((n) => connectedIds.has(n.id) || n._bucket).map((n) => ({ ...n })),
      links,
    }
    return result
  }, [docmapData, threshold])

  // KG mode: build force graph from entities + relationships
  const kgForceData = useMemo(() => {
    if (!kgData || mode !== "knowledge") return { nodes: [], links: [] }
    const nodes = kgData.entities.map((e) => ({
      id: `${e.name}::${e.entity_type}`,
      label: e.display_name,
      entity_type: e.entity_type,
      description: e.description,
      mention_count: e.mention_count,
      cluster_id: -1,
      chunk_count: e.mention_count,
      source_root: "",
      tags: [] as string[],
      headings: [] as string[],
      word_cloud: {} as Record<string, number>,
    }))
    const nodeIds = new Set(nodes.map((n) => n.id))
    const links = kgData.relationships
      .map((r) => ({
        source: `${r.source_name}::${r.source_type}`,
        target: `${r.target_name}::${r.target_type}`,
        rel_type: r.rel_type,
        weight: r.confidence,
      }))
      .filter((l) => nodeIds.has(l.source) && nodeIds.has(l.target))
    return { nodes, links }
  }, [kgData, mode])

  // Which data set to render
  const activeForceData = mode === "knowledge" ? kgForceData : forceDocMapData
  const isLoading = docmapStatus === "loading" || docmapStatus === "computing"
  const activeIsLoading = mode === "knowledge" ? kgLoading : isLoading
  const hasData =
    mode === "knowledge" ? kgData && kgData.entities.length > 0 : docmapData && docmapData.nodes.length > 0

  // Track whether the graph structure has changed (different documents),
  // vs cosmetic changes (threshold slider, word cloud toggle).
  // Only recenter when the node set actually changes.
  const prevDataId = useRef<string | null>(null)
  useEffect(() => {
    const dataId = docmapData ? `${docmapData.stats.doc_count}:${docmapData.stats.chunk_count}` : null
    if (dataId !== prevDataId.current) {
      const isFirstData = prevDataId.current === null
      prevDataId.current = dataId
      // Only recenter when doc/chunk counts change (scope switch, reindex),
      // not on initial load or word cloud toggles (same doc set).
      if (!isFirstData && initialFitDone.current && dataId !== null) {
        pendingRecenter.current = true
      }
    }
  }, [docmapData])

  // Configure d3 forces — spread slider scales all distances.
  // Runs on spread change AND data change (so forces are set on initial load),
  // but only reheats the simulation when spread actually changed.
  const prevSpreadRef = useRef(spread)
  useEffect(() => {
    const fg = fgRef.current
    if (!fg) return
    const s = spread / 100
    const charge = fg.d3Force("charge")
    if (charge) {
      charge.strength?.(-1500 * s)
      charge.distanceMax?.(2000 * s)
    }
    const link = fg.d3Force("link")
    if (link) {
      link.distance?.((l: GraphLink) => {
        const w = typeof l.weight === "number" ? l.weight : 0.5
        return (200 + (1 - w) * 800) * s
      })
      link.strength?.((l: GraphLink) => {
        const w = typeof l.weight === "number" ? l.weight : 0.5
        return w * 0.15
      })
    }
    const center = fg.d3Force("center")
    if (center) {
      center.strength?.(0.02)
    }
    prevSpreadRef.current = spread
    if (spreadInitialized.current) {
      fg.d3ReheatSimulation()
      if (initialFitDone.current) {
        pendingRecenter.current = true
      }
    }
    spreadInitialized.current = true
  }, [forceDocMapData, spread])

  // Active word cloud based on selection state
  const { activeWordCloud, wordCloudLabel } = useMemo(() => {
    if (!docmapData) return { activeWordCloud: {}, wordCloudLabel: "Terms" }

    if (selectedNodeId) {
      const node = docmapData.nodes.find((n) => n.id === selectedNodeId)
      if (node) {
        return {
          activeWordCloud: node.word_cloud,
          wordCloudLabel: `Terms: ${node.label}`,
        }
      }
    }

    if (searchTerm && highlightedNodes.size > 0) {
      const merged: Record<string, number> = {}
      for (const node of docmapData.nodes) {
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
      activeWordCloud: docmapData.global_word_cloud,
      wordCloudLabel: "Terms: All documents",
    }
  }, [docmapData, selectedNodeId, searchTerm, highlightedNodes])

  // Node color callback — bucket nodes get a distinct color
  const nodeColor = useCallback(
    (node: DocMapNode & { entity_type?: string; _bucket?: boolean }) => {
      if (mode === "knowledge" && node.entity_type) {
        if (hasHighlight && !highlightedNodes.has(node.id)) return colors.dim
        return ENTITY_TYPE_COLORS[node.entity_type] || UNCLUSTERED_COLOR
      }
      if (hasHighlight) {
        if (highlightedNodes.has(node.id)) {
          if (node.id === selectedNodeId) return HIGHLIGHT_COLOR
          if (node._bucket) return node.bucket_color ?? BUCKET_COLOR
          return (
            CLUSTER_COLORS[
              ((node.cluster_id % CLUSTER_COLORS.length) + CLUSTER_COLORS.length) % CLUSTER_COLORS.length
            ] || UNCLUSTERED_COLOR
          )
        }
        return colors.dim
      }
      if (node._bucket) return node.bucket_color ?? BUCKET_COLOR
      if (node.cluster_id < 0) return UNCLUSTERED_COLOR
      return CLUSTER_COLORS[node.cluster_id % CLUSTER_COLORS.length] || UNCLUSTERED_COLOR
      // docmapData is a phantom dep: its value isn't read here, but including it forces
      // the function ref to change when graph data updates, making the library re-apply
      // node colors (e.g. bucket vs non-bucket nodes flip styling on data refresh).
      // eslint-disable-next-line react-hooks/exhaustive-deps -- docmapData is a phantom dep to force color reapplication on data refresh
    },
    [mode, hasHighlight, highlightedNodes, selectedNodeId, colors.dim, docmapData],
  )

  // Node size: chunk count, enlarged when highlighted or bucket
  const nodeVal = useCallback(
    (node: DocMapNode) => {
      const base = Math.max(1, node.chunk_count)
      // Make bucket nodes larger so they're visible among hundreds of other nodes
      if (node._bucket) return Math.max(base * 3, 10)
      if (hasHighlight && highlightedNodes.has(node.id)) return base * 2
      return base
    },
    [hasHighlight, highlightedNodes],
  )

  // Node tooltip — escape user-controlled values to prevent XSS
  const nodeLabel = useCallback(
    (node: DocMapNode & { entity_type?: string; description?: string; mention_count?: number }) => {
      const esc = (s: string) =>
        s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;")
      if (mode === "knowledge" && node.entity_type) {
        const desc = node.description ? `<br/><span style="opacity:0.7">${esc(node.description)}</span>` : ""
        return `<div style="max-width:350px"><strong>${esc(node.label)}</strong><br/><span style="opacity:0.6">${esc(node.entity_type)}</span>${desc}<br/>${node.mention_count ?? 1} source${(node.mention_count ?? 1) !== 1 ? "s" : ""}</div>`
      }
      const dir = dirname(node.id)
      const tags = node.tags.length > 0 ? `<br/>Tags: ${esc(node.tags.join(", "))}` : ""
      return `<div style="max-width:350px"><strong>${esc(node.label)}</strong><br/><span style="opacity:0.7">${esc(dir)}</span><br/>${node.chunk_count} chunks${tags}</div>`
    },
    [mode],
  )

  // Link styling
  const linkColor = useCallback(
    (link: GraphLink & { rel_type?: string }) => {
      if (mode === "knowledge") {
        return `rgba(${colors.linkBase},0.35)`
      }
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
    },
    [mode, hasHighlight, highlightedNodes, colors],
  )

  const linkWidth = useCallback((link: GraphLink) => {
    const w = typeof link.weight === "number" ? link.weight : 0.5
    return Math.max(0.5, w * w * 8)
  }, [])

  // Node click
  const handleNodeClick = useCallback(
    (node: DocMapNode) => {
      selectNode(node.id)
      setViewingPath(node.id)
      setSelectedEdge(null)
    },
    [selectNode],
  )

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
  const handleTermClick = useCallback(
    (term: string) => {
      setSearchTerm(term)
      selectNode(null)
    },
    [setSearchTerm, selectNode],
  )

  const handleSearchChange = useCallback(
    (term: string) => {
      setSearchTerm(term)
      selectNode(null)
    },
    [setSearchTerm, selectNode],
  )

  const handleVisualizationRefresh = useCallback(() => {
    if (mode === "knowledge") {
      fetchKG()
    } else {
      fetchDocMap(scopeIdsParam, true, wordClouds, adHocTagsParam, selectedBucketIdsArray, bucketThreshold)
    }
  }, [mode, fetchKG, fetchDocMap, scopeIdsParam, wordClouds, adHocTagsParam, selectedBucketIdsArray, bucketThreshold])

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <VisualizationSidebar
        scopes={scopes}
        selectedScopeIds={selectedScopeIds}
        onScopeChange={handleScopeChange}
        availableTags={availableTags}
        selectedTags={selectedTags}
        onTagChange={handleTagChange}
        buckets={buckets}
        selectedBucketIds={selectedBucketIds}
        onBucketChange={handleBucketChange}
        threshold={threshold}
        onThresholdChange={setThreshold}
        spread={spread}
        onSpreadChange={setSpread}
        bucketThreshold={bucketThreshold}
        onBucketThresholdChange={setBucketThreshold}
        hasBucket={!!selectedBucketIdsArray}
        searchTerm={searchTerm}
        onSearchChange={handleSearchChange}
        onRefresh={handleVisualizationRefresh}
        isLoading={activeIsLoading}
        wordCloudsEnabled={wordClouds}
        onWordCloudsChange={setWordClouds}
        activeWordCloud={activeWordCloud}
        wordCloudLabel={wordCloudLabel}
        onTermClick={handleTermClick}
        mode={mode}
        kgData={kgData}
        extraction={extraction}
        onStartExtraction={startExtraction}
        onCancelExtraction={cancelExtraction}
      />

      <div ref={containerRef} className="flex-1 min-w-0 min-h-0 relative bg-background">
        {/* Staleness indicator */}
        {isStale && (
          <div className="absolute top-3 right-3 z-10 flex items-center gap-2 bg-yellow-500/10 border border-yellow-500/30 rounded-md px-3 py-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-yellow-500" />
            <span className="text-xs text-yellow-500">Data may be outdated</span>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs text-yellow-500"
              onClick={() =>
                fetchDocMap(scopeIdsParam, true, wordClouds, adHocTagsParam, selectedBucketIdsArray, bucketThreshold)
              }
            >
              Refresh
            </Button>
          </div>
        )}

        {/* Stats bar */}
        {!activeIsLoading && hasData && (
          <div className="absolute top-3 left-3 z-10 text-xs text-muted-foreground bg-background/80 rounded px-2 py-1">
            {mode === "knowledge"
              ? `${kgForceData.nodes.length} entities · ${kgForceData.links.length} relationships`
              : `${forceDocMapData.nodes.length}/${docmapData?.stats.doc_count ?? 0} docs${docmapData?.stats.bucket_doc_count ? ` (${docmapData.stats.bucket_doc_count} from bucket)` : ""} · ${forceDocMapData.links.length} edges`}
          </div>
        )}

        {/* Loading state with progress */}
        {activeIsLoading && (
          <div className="absolute inset-0 flex items-center justify-center z-10 bg-background/50">
            <div className="flex flex-col items-center gap-3 text-muted-foreground w-64">
              <div className="flex items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>
                  {docmapStatus === "computing"
                    ? mode === "knowledge"
                      ? "Loading knowledge graph..."
                      : "Computing document map..."
                    : "Loading..."}
                </span>
              </div>
              {docmapStatus === "computing" && progress.phase !== "idle" && (
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
        {!activeIsLoading && docmapStatus !== "checking-cache" && !hasData && mode === "similarity" && !docmapData && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-muted-foreground space-y-3">
              <p className="text-sm font-medium">Document map not built yet</p>
              <p className="text-xs">Build the document map to visualize document relationships</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  fetchDocMap(scopeIdsParam, true, wordClouds, adHocTagsParam, selectedBucketIdsArray, bucketThreshold)
                }
              >
                Build Doc Map
              </Button>
            </div>
          </div>
        )}

        {!activeIsLoading && !hasData && mode === "knowledge" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-muted-foreground space-y-3">
              <p className="text-sm font-medium">Knowledge graph is empty</p>
              <p className="text-xs">Use "Extract Entities" in the sidebar to build the knowledge graph</p>
            </div>
          </div>
        )}

        {/* Empty state — no documents at all */}
        {!activeIsLoading && docmapData && docmapData.nodes.length === 0 && mode === "similarity" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <p className="text-sm">No documents found</p>
              <p className="text-xs mt-1">Index some documents first, or change the scope filter</p>
            </div>
          </div>
        )}

        {/* Documents found but all filtered by threshold (no edges) */}
        {!activeIsLoading &&
          docmapData &&
          docmapData.nodes.length > 0 &&
          forceDocMapData.nodes.length === 0 &&
          mode === "similarity" && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center text-muted-foreground space-y-2">
                <p className="text-sm">
                  {docmapData.nodes.length} document{docmapData.nodes.length === 1 ? "" : "s"} found, but no similarity
                  connections at this threshold
                </p>
                <p className="text-xs">
                  Try lowering the similarity threshold, or broaden the scope to include more documents
                </p>
              </div>
            </div>
          )}

        {/* WebGL unavailable fallback */}
        {!webglSupported && hasData && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center text-muted-foreground max-w-md space-y-3">
              <MonitorX className="h-10 w-10 mx-auto text-muted-foreground/60" />
              <p className="text-sm font-medium">WebGL is not available</p>
              <p className="text-xs leading-relaxed">
                The 3D visualization requires WebGL, which needs hardware GPU access. This can happen with remote
                desktop sessions or systems without a GPU driver. Try accessing this page from a local browser session.
              </p>
              <p className="text-xs text-muted-foreground/60">
                {docmapData?.stats.doc_count ?? 0} docs · {docmapData?.stats.chunk_count ?? 0} chunks ·{" "}
                {docmapData?.stats.edge_count ?? 0} edges ready to visualize
              </p>
            </div>
          </div>
        )}

        {webglSupported && hasData && (
          <TypedForceGraph3D
            ref={fgRef}
            graphData={activeForceData}
            width={dimensions.width}
            height={dimensions.height}
            backgroundColor={colors.bg}
            nodeId="id"
            nodeLabel={nodeLabel}
            nodeColor={nodeColor}
            nodeVal={nodeVal}
            linkColor={linkColor}
            linkWidth={linkWidth}
            onNodeClick={handleNodeClick}
            onLinkClick={handleLinkClick}
            nodeOpacity={0.9}
            nodeResolution={12}
            linkOpacity={0.6}
            linkDirectionalArrowLength={mode === "knowledge" ? 6 : 0}
            linkDirectionalArrowRelPos={1}
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
              } else if (pendingRecenter.current) {
                pendingRecenter.current = false
                fgRef.current?.zoomToFit(400, 60)
              }
            }}
          />
        )}

        {/* Zoom controls */}
        {webglSupported && hasData && !activeIsLoading && (
          <VisualizationControls
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
            bucketId={selectedBucketIdsArray?.[0] ?? null}
            onClose={() => setSelectedEdge(null)}
            onDocClick={(path) => setViewingPath(path)}
          />
        )}
      </div>

      <FileViewerDialog path={viewingPath} onClose={() => setViewingPath(null)} />
    </div>
  )
}
