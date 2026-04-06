import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Loader2, X, FileText } from "lucide-react"
import type { EdgeDetail } from "@/lib/types"

export function EdgeDetailPanel({
  source,
  target,
  weight,
  onClose,
  onDocClick,
}: {
  source: string
  target: string
  weight: number
  onClose: () => void
  onDocClick: (path: string) => void
}) {
  const [detail, setDetail] = useState<EdgeDetail | null>(null)
  const [loading, setLoading] = useState(true) // starts true; reset via key prop on parent
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const params = new URLSearchParams({ source, target, top_k: "5" })
    api.get<EdgeDetail>(`/api/docmap/edge-detail?${params}`)
      .then((data) => {
        if (!cancelled) setDetail(data)
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [source, target])

  return (
    <div className="absolute bottom-3 right-3 z-20 w-[420px] max-h-[60%] bg-background border rounded-lg shadow-lg flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b shrink-0">
        <div className="min-w-0 space-y-0.5">
          <button
            onClick={() => onDocClick(source)}
            title={source}
            className="flex items-center gap-1 text-xs font-medium hover:underline text-left cursor-pointer max-w-full overflow-hidden"
          >
            <FileText className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="truncate">{source}</span>
          </button>
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <span>&harr;</span>
          </div>
          <button
            onClick={() => onDocClick(target)}
            title={target}
            className="flex items-center gap-1 text-xs font-medium hover:underline text-left cursor-pointer max-w-full overflow-hidden"
          >
            <FileText className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="truncate">{target}</span>
          </button>
          <p className="text-[10px] text-muted-foreground">
            Similarity: {weight.toFixed(4)}
            {detail && <span> · {detail.source_chunks} &times; {detail.target_chunks} chunks</span>}
          </p>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground ml-2 shrink-0 cursor-pointer">
          <X className="h-4 w-4" />
        </button>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="px-3 py-3 space-y-3">
          {loading && (
            <div className="flex items-center justify-center py-6 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              <span className="text-xs">Loading chunk pairs...</span>
            </div>
          )}

          {error && (
            <p className="text-xs text-destructive">Failed to load: {error}</p>
          )}

          {detail && detail.pairs.length === 0 && (
            <p className="text-xs text-muted-foreground">No chunk pairs found.</p>
          )}

          {detail && detail.pairs.map((pair, i) => (
            <div key={i} className="border rounded-md p-2.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-medium text-muted-foreground">
                  Pair {i + 1}
                </span>
                <span className="text-[10px] font-mono text-muted-foreground">
                  {pair.similarity.toFixed(4)}
                </span>
              </div>
              <div className="space-y-1.5 overflow-hidden">
                <div>
                  <button
                    onClick={() => onDocClick(source)}
                    title={source}
                    className="text-[10px] text-muted-foreground mb-0.5 hover:underline cursor-pointer truncate w-full block text-left"
                  >
                    {source}
                  </button>
                  <p className="text-xs leading-relaxed bg-muted/50 rounded px-2 py-1.5 whitespace-pre-wrap">
                    {pair.source_text}
                  </p>
                </div>
                <div>
                  <button
                    onClick={() => onDocClick(target)}
                    title={target}
                    className="text-[10px] text-muted-foreground mb-0.5 hover:underline cursor-pointer truncate w-full block text-left"
                  >
                    {target}
                  </button>
                  <p className="text-xs leading-relaxed bg-muted/50 rounded px-2 py-1.5 whitespace-pre-wrap">
                    {pair.target_text}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
