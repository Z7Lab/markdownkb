import { useCallback, useState } from "react"
import { type Bucket, type useBuckets, useBucketFiles } from "@/hooks/use-buckets"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { relativeTime } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Pencil, Trash2, FileText, Loader2, Clock,
  Infinity as InfinityIcon, RefreshCw,
} from "lucide-react"
import { BucketEditForm } from "./bucket-edit-form"

export interface BucketDetailPanelProps {
  bucket: Bucket
  onDelete: (id: string) => void
  onViewFile: (path: string) => void
  updateBucket: ReturnType<typeof useBuckets>["updateBucket"]
  refresh: () => Promise<void>
}

export function BucketDetailPanel({
  bucket,
  onDelete,
  onViewFile,
  updateBucket,
  refresh,
}: BucketDetailPanelProps) {
  const { files, loading: loadingFiles, indexing: filesIndexing, reload: reloadFiles } = useBucketFiles(bucket.id)
  const [editing, setEditing] = useState(false)
  const [reindexing, setReindexing] = useState(false)

  const handleReindex = useCallback(async () => {
    setReindexing(true)
    const toastId = toast.loading(`Reindexing "${bucket.name}"...`)
    try {
      const res = await api.post<{ added_files: number; added_chunks: number }>(
        `/api/v1/buckets/${bucket.id}/reindex`, {}
      )
      await refresh()
      toast.success(`Reindexed "${bucket.name}"`, {
        id: toastId,
        description: `${res.added_files} file${res.added_files !== 1 ? "s" : ""}, ${res.added_chunks} chunk${res.added_chunks !== 1 ? "s" : ""} added`,
        duration: 4000,
      })
      reloadFiles()
    } catch (err) {
      toast.error(`Reindex failed: ${(err as Error).message}`, { id: toastId })
    } finally {
      setReindexing(false)
    }
  }, [bucket.id, bucket.name, refresh, reloadFiles])

  const sources = (() => {
    try { return JSON.parse(bucket.sources) as { path: string; glob?: string }[] }
    catch { return [] }
  })()

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-6 space-y-4">
          {/* Header */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="h-3 w-3 rounded-full shrink-0 mt-0.5"
                style={{ backgroundColor: bucket.color ?? "var(--bucket-default)" }}
              />
              <div className="min-w-0">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  {bucket.name}
                  {bucket.indexing && (
                    <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-500/50 gap-1">
                      <Loader2 className="h-2.5 w-2.5 animate-spin" />
                      indexing
                    </Badge>
                  )}
                  {bucket.expired && (
                    <Badge variant="outline" className="text-[10px] text-destructive border-destructive/40">
                      expired
                    </Badge>
                  )}
                </h2>
                <div className="flex items-center gap-3 mt-0.5 text-xs text-muted-foreground">
                  <span>{bucket.file_count} files</span>
                  <span>{bucket.chunk_count} chunks</span>
                  <span>{relativeTime(bucket.created_at)}</span>
                  {bucket.expires_at && !bucket.expired && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      expires {new Date(bucket.expires_at + "Z").toLocaleDateString()}
                    </span>
                  )}
                  {!bucket.expires_at && !bucket.expired && (
                    <span className="flex items-center gap-1">
                      <InfinityIcon className="h-3 w-3" /> permanent
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                title="Edit bucket"
                onClick={() => setEditing(!editing)}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                title="Reindex from sources"
                disabled={reindexing}
                onClick={handleReindex}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${reindexing ? "animate-spin" : ""}`} />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                title="Delete bucket"
                onClick={() => onDelete(bucket.id)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          {/* Edit form */}
          {editing && (
            <BucketEditForm
              bucket={bucket}
              onSave={() => setEditing(false)}
              onCancel={() => setEditing(false)}
              updateBucket={updateBucket}
            />
          )}

          {/* Sources */}
          {sources.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Sources</p>
              <div className="space-y-0.5">
                {sources.map((s, i) => (
                  <p key={i} className="text-xs font-mono text-muted-foreground truncate">
                    {s.path}
                    {s.glob && s.glob !== "**/*.md" && (
                      <span className="text-muted-foreground/60 ml-2">{s.glob}</span>
                    )}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* Files table */}
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <p className="text-xs font-medium text-muted-foreground">
                Files {files.length > 0 && `(${files.length})`}
              </p>
              {filesIndexing && (
                <span className="text-[10px] text-amber-600 flex items-center gap-1">
                  <Loader2 className="h-2.5 w-2.5 animate-spin" />
                  Embedding in progress
                </span>
              )}
            </div>

            {loadingFiles && (
              <div className="flex items-center gap-2 py-6 justify-center text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Loading files...
              </div>
            )}

            {!loadingFiles && files.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-6">
                No files in this bucket
              </p>
            )}

            {!loadingFiles && files.length > 0 && (
              <div className="border rounded-md overflow-hidden">
                <div className="grid grid-cols-[1fr_auto] text-xs font-medium text-muted-foreground bg-muted/30 px-3 py-1.5 border-b">
                  <span>File</span>
                  <span>Chunks</span>
                </div>
                <div className="divide-y">
                  {files.map((f) => (
                    <button
                      key={f.path}
                      type="button"
                      className="w-full grid grid-cols-[1fr_auto] items-center px-3 py-2 text-xs hover:bg-accent text-left transition-colors"
                      onClick={() => onViewFile(f.path)}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <FileText className="h-3 w-3 text-muted-foreground shrink-0" />
                        <span className="truncate">
                          {f.title || f.path.split("/").pop()}
                        </span>
                      </div>
                      <span className="text-muted-foreground tabular-nums pl-4">
                        {f.chunk_count}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </ScrollArea>
    </div>
  )
}
