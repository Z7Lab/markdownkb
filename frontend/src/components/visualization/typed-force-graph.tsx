/**
 * Typed wrapper for react-force-graph-3d.
 *
 * The library's NodeObject/LinkObject generics don't structurally match our domain
 * types, so all usage in this file is the single point of type adaptation. This
 * isolates unsafe casts here rather than spreading `as never` / `as Record<string,unknown>`
 * throughout VisualizationTab.
 */
import { forwardRef } from "react"
import ForceGraph3D from "react-force-graph-3d"
import type { ForceGraphRef, DocMapNode } from "@/lib/types"

export interface GraphLink {
  source: string | { id: string }
  target: string | { id: string }
  weight: number
  rel_type?: string
}

export interface ForceGraphData {
  nodes: DocMapNode[]
  links: GraphLink[]
}

interface TypedForceGraph3DProps {
  graphData: ForceGraphData
  width: number
  height: number
  backgroundColor: string
  nodeId?: string
  nodeLabel: (node: DocMapNode & { entity_type?: string; description?: string; mention_count?: number }) => string
  nodeColor: (node: DocMapNode & { entity_type?: string; _bucket?: boolean }) => string
  nodeVal: (node: DocMapNode) => number
  nodeOpacity?: number
  nodeResolution?: number
  linkColor: (link: GraphLink) => string
  linkWidth: (link: GraphLink) => number
  linkOpacity?: number
  linkDirectionalArrowLength?: number
  linkDirectionalArrowRelPos?: number
  linkDirectionalParticles?: number
  onNodeClick: (node: DocMapNode) => void
  onLinkClick: (link: GraphLink) => void
  onBackgroundClick: () => void
  onEngineStop: () => void
  showNavInfo?: boolean
  enableNodeDrag?: boolean
  d3AlphaDecay?: number
  d3VelocityDecay?: number
  cooldownTicks?: number
  warmupTicks?: number
}

export const TypedForceGraph3D = forwardRef<ForceGraphRef, TypedForceGraph3DProps>(
  function TypedForceGraph3D(props, ref) {
    // Single boundary where domain types are adapted to the library's generic types.
    return (
      <ForceGraph3D
        ref={ref as never}
        {...(props as unknown as Record<string, unknown>)}
      />
    )
  },
)
