import { useCallback, useRef, useState } from "react"
import { type Bucket, type useBuckets, useBucketFiles } from "@/hooks/use-buckets"
import { api, getApiKey } from "@/lib/api"
import { toast } from "sonner"
import { relativeTime } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Pencil, Trash2, FileText, Loader2, Clock,
  Infinity as InfinityIcon, RefreshCw, Link, Upload,
} from "lucide-react"
import { BucketEditForm } from "./bucket-edit-form"

const SUPPORTED_EXTENSIONS = ".pdf,.docx,.pptx,.xlsx,.xls,.epub,.html,.htm,.csv,.txt,.rst,.rtf,.odt,.ipynb,.msg"

function filenameFromContent(hint: string, markdown: string): string {
  const titleMatch = /^#{1,3} (.+)$/m.exec(markdown)
  if (titleMatch?.[1]) {
    return titleMatch[1]
      .replace(/[^\w\s-]/g, "").trim()
      .replace(/\s+/g, "-").toLowerCase()
      .slice(0, 80) + ".md"
  }
  try {
    const { hostname, pathname } = new URL(hint)
    const slug = pathname.replace(/\//g, "-").replace(/[^\w-]/g, "").slice(0, 40)
    return `${hostname}${slug || ""}.md`
  } catch {
    const base = hint.split("/").pop()?.replace(/\.[^.]+$/, "") ?? "imported"
    return `${base}.md`
  }
}

function converterErrorMessage(msg: string): string {
  if (msg.includes("404") || msg.includes("Not Found"))
    return "Converter plugin is not enabled — enable it in Settings → Plugins"
  return `Import failed: ${msg}`
}

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

  // Import state
  const [clipUrl, setClipUrl] = useState("")
  const [clipping, setClipping] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<{ name: string; done: boolean; error?: string }[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const pushDocument = useCallback(async (name: string, markdown: string) => {
    await api.post(`/api/v1/buckets/${bucket.id}/documents`, {
      documents: [{ name, content: markdown }],
    })
  }, [bucket.id])

  const handleClip = useCallback(async () => {
    const url = clipUrl.trim()
    if (!url) return
    setClipping(true)
    try {
      const converted = await api.post<{ markdown: string }>("/api/v1/converter/url", { url })
      const name = filenameFromContent(url, converted.markdown)
      await pushDocument(name, converted.markdown)
      setClipUrl("")
      reloadFiles()
      toast.success(`Clipped "${name}"`)
    } catch (err) {
      toast.error(converterErrorMessage((err as Error).message))
    } finally {
      setClipping(false)
    }
  }, [clipUrl, pushDocument, reloadFiles])

  const handleFileUpload = useCallback(async (fileList: FileList) => {
    const files = Array.from(fileList)
    if (!files.length) return
    setUploading(true)
    setUploadProgress(files.map((f) => ({ name: f.name, done: false })))

    const key = getApiKey()
    const headers: Record<string, string> = key ? { "X-MarkdownKB-Key": key } : {}

    for (let i = 0; i < files.length; i++) {
      const file = files[i]!
      try {
        const fd = new FormData()
        fd.append("file", file)
        const res = await fetch("/api/v1/converter/upload", { method: "POST", headers, body: fd })
        if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
        const data = (await res.json()) as { markdown: string; filename: string }
        const name = filenameFromContent(file.name, data.markdown)
        await pushDocument(name, data.markdown)
        setUploadProgress((prev) => prev.map((p, j) => j === i ? { ...p, done: true } : p))
      } catch (err) {
        const msg = (err as Error).message
        setUploadProgress((prev) => prev.map((p, j) => j === i ? { ...p, done: true, error: msg } : p))
      }
    }

    reloadFiles()
    setUploading(false)
    if (fileInputRef.current) fileInputRef.current.value = ""

    const succeeded = uploadProgress.filter((p) => p.done && !p.error).length
    const failed = uploadProgress.filter((p) => p.error).length
    if (failed === 0) toast.success(`Imported ${files.length} file${files.length !== 1 ? "s" : ""}`)
    else toast.warning(`${succeeded} imported, ${failed} failed`)
  }, [pushDocument, reloadFiles, uploadProgress])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files.length) void handleFileUpload(e.dataTransfer.files)
  }, [handleFileUpload])

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

  const importing = clipping || uploading

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
                aria-label="Edit bucket"
                onClick={() => setEditing(!editing)}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                aria-label="Reindex from sources"
                disabled={reindexing}
                onClick={handleReindex}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${reindexing ? "animate-spin" : ""}`} />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                aria-label="Delete bucket"
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

          {/* Import */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground">Import</p>

            {/* URL clip */}
            <div className="flex gap-2">
              <Input
                value={clipUrl}
                onChange={(e) => setClipUrl(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") void handleClip() }}
                placeholder="Paste a URL (YouTube, article, docs…)"
                className="h-8 text-xs"
                disabled={importing}
                aria-label="URL to import"
              />
              <Button
                size="sm"
                variant="outline"
                className="h-8 shrink-0"
                onClick={handleClip}
                disabled={importing || !clipUrl.trim()}
              >
                {clipping ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Link className="h-3.5 w-3.5" />}
                <span className="ml-1.5">{clipping ? "Clipping…" : "Clip"}</span>
              </Button>
            </div>

            {/* File drop zone */}
            <div
              className="border border-dashed rounded-md px-3 py-4 text-center cursor-pointer hover:bg-accent/50 transition-colors"
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => !importing && fileInputRef.current?.click()}
              aria-label="Drop files to import"
            >
              {uploading ? (
                <div className="space-y-1">
                  {uploadProgress.map((p) => (
                    <div key={p.name} className="flex items-center gap-2 text-xs justify-center">
                      {p.done
                        ? p.error
                          ? <span className="text-destructive truncate max-w-[200px]">{p.name} — {p.error}</span>
                          : <span className="text-green-600 truncate max-w-[200px]">✓ {p.name}</span>
                        : <><Loader2 className="h-3 w-3 animate-spin shrink-0" /><span className="truncate max-w-[200px] text-muted-foreground">{p.name}</span></>
                      }
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center gap-1 text-muted-foreground pointer-events-none">
                  <Upload className="h-4 w-4" />
                  <p className="text-xs">Drop files or click to browse</p>
                  <p className="text-[10px]">PDF, Word, PowerPoint, Excel, EPUB and more</p>
                </div>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={SUPPORTED_EXTENSIONS}
              className="hidden"
              onChange={(e) => { if (e.target.files?.length) void handleFileUpload(e.target.files) }}
            />
          </div>

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
