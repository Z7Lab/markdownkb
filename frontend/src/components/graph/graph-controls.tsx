import { useCallback } from "react"
import { Plus, Minus, Maximize, X } from "lucide-react"
import type { ForceGraphRef } from "@/lib/types"

export function GraphControls({
  fgRef,
  hasSelection,
  onClearSelection,
}: {
  fgRef: React.RefObject<ForceGraphRef | null>
  hasSelection?: boolean
  onClearSelection?: () => void
}) {
  const zoom = useCallback((factor: number) => {
    const fg = fgRef.current
    if (!fg) return
    const pos = fg.cameraPosition()
    fg.cameraPosition(
      { x: pos.x * factor, y: pos.y * factor, z: pos.z * factor },
      undefined,
      300,
    )
  }, [fgRef])

  const zoomToFit = useCallback(() => {
    fgRef.current?.zoomToFit(400, 60)
  }, [fgRef])

  return (
    <div className="absolute bottom-3 left-3 z-20 flex flex-col gap-0.5 bg-background/80 backdrop-blur-sm border rounded-lg p-0.5">
      <button
        onClick={() => zoom(0.7)}
        aria-label="Zoom in"
        className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
      >
        <Plus className="h-3.5 w-3.5" />
      </button>
      <button
        onClick={() => zoom(1.4)}
        aria-label="Zoom out"
        className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
      >
        <Minus className="h-3.5 w-3.5" />
      </button>
      <div className="border-t mx-1" />
      <button
        onClick={zoomToFit}
        aria-label="Fit to view"
        className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
      >
        <Maximize className="h-3.5 w-3.5" />
      </button>
      {hasSelection && (
        <>
          <div className="border-t mx-1" />
          <button
            onClick={onClearSelection}
            aria-label="Clear selection"
            className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </>
      )}
    </div>
  )
}
