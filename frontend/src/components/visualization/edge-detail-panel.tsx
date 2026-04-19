import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Loader2, X, FileText, Sparkles } from "lucide-react"
import type { EdgeDetail } from "@/lib/types"

function basename(p: string): string {
  const i = p.lastIndexOf("/")
  return i >= 0 ? p.slice(i + 1) : p
}

function pct(val: number): string {
  return `${(val * 100).toFixed(1)}%`
}

export function EdgeDetailPanel({
  source,
  target,
  weight,
  bucketId,
  onClose,
  onDocClick,
}: {
  source: string
  target: string
  weight: number
  bucketId: string | null
  onClose: () => void
  onDocClick: (path: string) => void
}) {
  const [detail, setDetail] = useState<EdgeDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [explanation, setExplanation] = useState<string | null>(null)
  const [explainLoading, setExplainLoading] = useState(false)
  const [explainError, setExplainError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState("0")

  useEffect(() => {
    let cancelled = false
    setExplanation(null)
    setExplainError(null)
    setExplainLoading(false)
    setActiveTab("0")

    const params = new URLSearchParams({ source, target, top_k: "5" })
    if (bucketId) params.set("bucket_id", bucketId)
    api.get<EdgeDetail>(`/api/v1/docmap/edge-detail?${params}`)
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
  }, [source, target, bucketId])

  const handleExplain = async () => {
    setExplainLoading(true)
    setExplainError(null)
    try {
      const params = new URLSearchParams({ source, target })
      if (bucketId) params.set("bucket_id", bucketId)
      const resp = await api.get<{ explanation: string; cached: boolean }>(
        `/api/v1/docmap/edge-explain?${params}`,
      )
      setExplanation(resp.explanation)
    } catch (err) {
      setExplainError((err as Error).message)
    } finally {
      setExplainLoading(false)
    }
  }

  return (
    <div className="absolute bottom-3 right-3 z-20 w-[min(480px,calc(100vw-24px))] max-h-[70vh] bg-background border rounded-lg shadow-lg flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 px-3 py-2 border-b shrink-0">
        <div className="min-w-0 flex-1 space-y-1">
          <button
            onClick={() => onDocClick(source)}
            title={source}
            className="flex items-center gap-1.5 text-xs font-medium hover:underline text-left cursor-pointer w-full"
          >
            <FileText className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="truncate">{basename(source)}</span>
          </button>
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground pl-4">
            <span>↔</span>
            <span>Similarity: {pct(weight)}</span>
            {detail && <span>· {detail.source_chunks}×{detail.target_chunks} chunks</span>}
          </div>
          <button
            onClick={() => onDocClick(target)}
            title={target}
            className="flex items-center gap-1.5 text-xs font-medium hover:underline text-left cursor-pointer w-full"
          >
            <FileText className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="truncate">{basename(target)}</span>
          </button>
        </div>
        <button
          onClick={onClose}
          aria-label="Close"
          className="text-muted-foreground hover:text-foreground shrink-0 cursor-pointer mt-0.5"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Scrollable body */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="px-3 py-3 space-y-3">
          {/* Explain block */}
          {explanation ? (
            <div className="text-xs leading-relaxed bg-primary/5 border border-primary/20 rounded px-2.5 py-2 flex gap-2">
              <Sparkles className="h-3.5 w-3.5 shrink-0 mt-0.5 text-primary" />
              <p className="break-words min-w-0">{explanation}</p>
            </div>
          ) : explainError ? (
            <div className="flex items-center gap-2">
              <p className="text-[11px] text-destructive break-words flex-1">
                Explain failed: {explainError}
              </p>
              <button
                onClick={handleExplain}
                className="text-[10px] px-2 py-0.5 rounded border hover:bg-accent cursor-pointer shrink-0"
              >
                Retry
              </button>
            </div>
          ) : (
            <button
              onClick={handleExplain}
              disabled={explainLoading}
              className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded border border-primary/30 text-primary hover:bg-primary/10 disabled:opacity-50 cursor-pointer disabled:cursor-wait"
            >
              {explainLoading ? (
                <><Loader2 className="h-3 w-3 animate-spin" /> Analyzing…</>
              ) : (
                <><Sparkles className="h-3 w-3" /> Why are these connected?</>
              )}
            </button>
          )}

          {loading && (
            <div className="flex items-center justify-center py-6 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              <span className="text-xs">Loading chunk pairs…</span>
            </div>
          )}

          {error && (
            <p className="text-xs text-destructive break-words">Failed to load: {error}</p>
          )}

          {detail && detail.pairs.length === 0 && !loading && (
            <p className="text-xs text-muted-foreground">No chunk pairs found.</p>
          )}

          {detail && detail.pairs.length > 0 && (
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="h-7 gap-0.5">
                {detail.pairs.map((pair, i) => (
                  <TabsTrigger key={i} value={String(i)} className="h-6 px-2 text-[11px]">
                    {i + 1}
                    <span className="ml-1 text-muted-foreground font-normal">{pct(pair.similarity)}</span>
                  </TabsTrigger>
                ))}
              </TabsList>

              {detail.pairs.map((pair, i) => (
                <TabsContent key={i} value={String(i)} className="mt-2 space-y-2">
                  <div className="min-w-0">
                    <button
                      onClick={() => onDocClick(source)}
                      title={source}
                      className="text-[10px] text-muted-foreground mb-1 hover:underline cursor-pointer truncate block w-full text-left"
                    >
                      {basename(source)}
                    </button>
                    <p className="text-xs leading-relaxed bg-muted/50 rounded px-2 py-1.5 whitespace-pre-wrap break-words">
                      {pair.source_text}
                    </p>
                  </div>
                  <div className="min-w-0">
                    <button
                      onClick={() => onDocClick(target)}
                      title={target}
                      className="text-[10px] text-muted-foreground mb-1 hover:underline cursor-pointer truncate block w-full text-left"
                    >
                      {basename(target)}
                    </button>
                    <p className="text-xs leading-relaxed bg-muted/50 rounded px-2 py-1.5 whitespace-pre-wrap break-words">
                      {pair.target_text}
                    </p>
                  </div>
                </TabsContent>
              ))}
            </Tabs>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
