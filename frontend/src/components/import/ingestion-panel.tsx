import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { slugifyFilename } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Progress } from "@/components/ui/progress"
import {
  Loader2, Link as LinkIcon, Upload, FilePlus, FileText, AudioLines, AlertCircle,
} from "lucide-react"

export type IngestDestination =
  | { type: "source"; path: string }
  | { type: "bucket"; id: string }

interface FormatInfo {
  label: string
  extensions: string[]
  available: boolean
}

interface ImportMethod {
  id: string
  label: string
  available: boolean
  reason: string | null
  accept?: string
  formats?: FormatInfo[]
  transcript_support?: boolean
  provider?: string
  model?: string
  model_ready?: boolean
}

interface ProgressItem {
  name: string
  done: boolean
  error?: string
  progress?: number
  message?: string
}

export interface IngestionPanelProps {
  destination: IngestDestination
  /** Called after one or more items are successfully ingested. */
  onIngested?: () => void
}

function isYouTubeUrl(url: string): boolean {
  return /youtube\.com\/|youtu\.be\//.test(url)
}

/** Derive a filename from converted markdown (heading) or the source hint. */
function filenameFromContent(hint: string, markdown: string): string {
  const titleMatch = /^#{1,3} (.+)$/m.exec(markdown)
  if (titleMatch?.[1]) {
    return slugifyFilename(titleMatch[1]) + ".md"
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
  if (msg.includes("403") || msg.includes("Forbidden"))
    return "Import failed: the site blocked the request (403 Forbidden). Try downloading the page and uploading the file instead."
  if (msg.includes("401") || msg.includes("Unauthorized"))
    return "Import failed: the URL requires authentication (401). Download the file and upload it instead."
  return `Import failed: ${msg}`
}

interface IngestStatus {
  running: boolean
  progress: number
  message: string
  result: { filename: string } | null
  error: string | null
}

/** Poll an async ingest job until it finishes; resolves with the result. */
async function pollIngestJob(
  jobId: string,
  onProgress: (progress: number, message: string) => void,
): Promise<{ filename: string }> {
  for (;;) {
    const s = await api.get<IngestStatus>(`/api/v1/converter/ingest/status/${jobId}`)
    if (!s.running) {
      if (s.error) throw new Error(s.error)
      return { filename: s.result?.filename ?? "file" }
    }
    onProgress(s.progress ?? 0, s.message ?? "")
    await new Promise((r) => setTimeout(r, 1000))
  }
}

export function IngestionPanel({ destination, onIngested }: IngestionPanelProps) {
  const [methods, setMethods] = useState<ImportMethod[] | null>(null)
  const [clipUrl, setClipUrl] = useState("")
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState<ProgressItem[]>([])
  const [createName, setCreateName] = useState("")
  const [createBody, setCreateBody] = useState("")
  const [creating, setCreating] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let active = true
    api.get<{ methods: ImportMethod[] }>("/api/v1/import/capabilities")
      .then((r) => { if (active) setMethods(r.methods) })
      .catch(() => { if (active) setMethods([]) })
    return () => { active = false }
  }, [])

  const find = (id: string) => methods?.find((m) => m.id === id)
  const fileMethod = find("file_upload")
  const urlMethod = find("url_clip")
  const audioMethod = find("audio")
  const createMethod = find("create_markdown")

  const pushToBucket = useCallback(async (name: string, content: string) => {
    if (destination.type !== "bucket") return
    await api.post(`/api/v1/buckets/${destination.id}/documents`, {
      documents: [{ name, content }],
    })
  }, [destination])

  const handleFiles = useCallback(async (fileList: FileList) => {
    const files = Array.from(fileList)
    if (!files.length) return
    setBusy(true)
    setProgress(files.map((f) => ({ name: f.name, done: false })))
    let ok = 0
    let fail = 0
    for (let i = 0; i < files.length; i++) {
      const file = files[i]!
      const mark = (patch: Partial<ProgressItem>) =>
        setProgress((prev) => prev.map((p, j) => (j === i ? { ...p, ...patch } : p)))
      try {
        if (destination.type === "source") {
          const fd = new FormData()
          fd.append("file", file)
          fd.append("destination", destination.path)
          const { job_id } = await api.upload<{ job_id: string }>("/api/v1/converter/ingest", fd)
          await pollIngestJob(job_id, (p, msg) => mark({ progress: p, message: msg }))
        } else if (file.name.toLowerCase().endsWith(".md")) {
          await pushToBucket(file.name, await file.text())
        } else {
          const fd = new FormData()
          fd.append("file", file)
          const data = await api.upload<{ markdown: string; filename: string }>("/api/v1/converter/upload", fd)
          await pushToBucket(filenameFromContent(file.name, data.markdown), data.markdown)
        }
        mark({ done: true, progress: 1 })
        ok++
      } catch (err) {
        mark({ done: true, error: (err as Error).message })
        fail++
      }
    }
    setBusy(false)
    if (fileInputRef.current) fileInputRef.current.value = ""
    if (fail === 0) toast.success(`Imported ${ok} file${ok !== 1 ? "s" : ""}`)
    else if (ok === 0) toast.error(`Import failed for all ${fail} file${fail !== 1 ? "s" : ""}`)
    else toast.warning(`${ok} imported, ${fail} failed`)
    if (ok > 0) onIngested?.()
  }, [destination, pushToBucket, onIngested])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    if (!busy && e.dataTransfer.files.length) void handleFiles(e.dataTransfer.files)
  }, [busy, handleFiles])

  const handleClip = useCallback(async () => {
    const url = clipUrl.trim()
    if (!url) return
    setBusy(true)
    setProgress([{ name: url, done: false }])
    try {
      if (destination.type === "source") {
        const fd = new FormData()
        fd.append("url", url)
        fd.append("destination", destination.path)
        const { job_id } = await api.upload<{ job_id: string }>("/api/v1/converter/ingest", fd)
        await pollIngestJob(job_id, (p, msg) =>
          setProgress([{ name: url, done: false, progress: p, message: msg }]))
      } else {
        const converted = await api.post<{ markdown: string; title?: string }>("/api/v1/converter/url", { url })
        const name = converted.title
          ? slugifyFilename(converted.title) + ".md"
          : filenameFromContent(url, converted.markdown)
        await pushToBucket(name, converted.markdown)
      }
      setProgress([{ name: url, done: true, progress: 1 }])
      setClipUrl("")
      toast.success("Clipped to knowledge base")
      onIngested?.()
    } catch (err) {
      setProgress([{ name: url, done: true, error: (err as Error).message }])
      toast.error(converterErrorMessage((err as Error).message))
    } finally {
      setBusy(false)
    }
  }, [clipUrl, destination, pushToBucket, onIngested])

  const handleCreate = useCallback(async () => {
    const name = createName.trim()
    if (!name || !createBody.trim()) return
    const filename = name.toLowerCase().endsWith(".md") ? name : slugifyFilename(name) + ".md"
    setCreating(true)
    try {
      if (destination.type === "source") {
        await api.post("/api/v1/documents", {
          path: filename, content: createBody, source: destination.path,
        })
      } else {
        await pushToBucket(filename, createBody)
      }
      setCreateName("")
      setCreateBody("")
      toast.success(`Created "${filename}"`)
      onIngested?.()
    } catch (err) {
      toast.error(`Create failed: ${(err as Error).message}`)
    } finally {
      setCreating(false)
    }
  }, [createName, createBody, destination, pushToBucket, onIngested])

  if (methods === null) {
    return (
      <div className="flex items-center gap-2 py-8 justify-center text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading import options…
      </div>
    )
  }

  const anyAvailable = methods.some((m) => m.available)
  if (!anyAvailable) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-center text-sm text-muted-foreground">
        <AlertCircle className="h-5 w-5" />
        <p>No import methods are available.</p>
        <p className="text-xs">Enable converter formats or audio transcription in Settings → File Converter.</p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* File upload */}
      {fileMethod?.available && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Upload a file</p>
          <div
            className="border border-dashed rounded-md px-3 py-5 text-center cursor-pointer hover:bg-accent/50 transition-colors"
            role="button"
            tabIndex={0}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => !busy && fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault()
                if (!busy) fileInputRef.current?.click()
              }
            }}
            aria-label="Drop files to import"
          >
            {busy && progress.length > 0 ? (
              <div className="space-y-1.5">
                {progress.map((p) => (
                  <div key={p.name} className="text-xs">
                    <div className="flex items-center gap-2 justify-center">
                      {p.done ? (
                        p.error ? (
                          <span className="text-destructive truncate max-w-[260px]">{p.name} — {p.error}</span>
                        ) : (
                          <span className="text-green-600 truncate max-w-[260px]">✓ {p.name}</span>
                        )
                      ) : (
                        <>
                          <Loader2 className="h-3 w-3 animate-spin shrink-0" />
                          <span className="truncate max-w-[260px] text-muted-foreground">
                            {p.message || p.name}
                          </span>
                        </>
                      )}
                    </div>
                    {!p.done && typeof p.progress === "number" && p.progress > 0 && (
                      <Progress value={p.progress * 100} className="h-1 mt-1" />
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-1.5 text-muted-foreground pointer-events-none">
                <Upload className="h-4 w-4" />
                <p className="text-xs">Drop files or click to browse</p>
                {fileMethod.formats && fileMethod.formats.length > 0 && (
                  <div className="flex flex-wrap justify-center gap-1 mt-0.5">
                    {fileMethod.formats.map((f) => (
                      <span
                        key={f.label}
                        className={`text-[10px] px-1.5 py-0.5 rounded border ${
                          f.available
                            ? "border-green-500/40 text-green-700 dark:text-green-400 bg-green-500/10"
                            : "border-muted text-muted-foreground/50 bg-muted/30"
                        }`}
                        title={f.available ? `${f.extensions.join(", ")} — available` : `${f.extensions.join(", ")} — not enabled`}
                      >
                        {f.label}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={fileMethod.accept || undefined}
            className="hidden"
            onChange={(e) => { if (e.target.files?.length) void handleFiles(e.target.files) }}
          />
          {/* Audio status hint */}
          {audioMethod && (
            <p className={`text-[11px] flex items-center gap-1 ${audioMethod.available ? "text-muted-foreground" : "text-amber-600 dark:text-amber-400"}`}>
              <AudioLines className="h-3 w-3 shrink-0" />
              {audioMethod.available
                ? `Audio transcription ready (${audioMethod.provider === "remote" ? "remote API" : `local model "${audioMethod.model}"`})`
                : `Audio: ${audioMethod.reason}`}
            </p>
          )}
        </div>
      )}

      {/* URL clip */}
      {urlMethod?.available && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Clip from the web</p>
          <div className="flex gap-2">
            <Input
              value={clipUrl}
              onChange={(e) => setClipUrl(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") void handleClip() }}
              placeholder="Paste a URL (YouTube, article, docs…)"
              className="h-8 text-xs"
              disabled={busy}
              aria-label="URL to import"
            />
            <Button
              size="sm"
              variant="outline"
              className="h-8 shrink-0"
              onClick={handleClip}
              disabled={busy || !clipUrl.trim()}
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <LinkIcon className="h-3.5 w-3.5" />}
              <span className="ml-1.5">Clip</span>
            </Button>
          </div>
          {urlMethod.transcript_support === false && isYouTubeUrl(clipUrl) && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              YouTube transcript extraction requires the <strong>full</strong> image — only page metadata will be captured.
            </p>
          )}
        </div>
      )}

      {/* Create markdown */}
      {createMethod?.available && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Create a markdown note</p>
          <Input
            value={createName}
            onChange={(e) => setCreateName(e.target.value)}
            placeholder="Filename (e.g. meeting-notes)"
            className="h-8 text-xs"
            disabled={creating}
            aria-label="New document filename"
          />
          <Textarea
            value={createBody}
            onChange={(e) => setCreateBody(e.target.value)}
            placeholder="Write markdown content…"
            className="min-h-[120px] text-xs font-mono"
            disabled={creating}
            aria-label="New document content"
          />
          <div className="flex justify-end">
            <Button
              size="sm"
              variant="outline"
              className="h-8"
              onClick={handleCreate}
              disabled={creating || !createName.trim() || !createBody.trim()}
            >
              {creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FilePlus className="h-3.5 w-3.5" />}
              <span className="ml-1.5">Create</span>
            </Button>
          </div>
        </div>
      )}

      {/* Unavailable-method hints (so users know what setup unlocks) */}
      {(urlMethod && !urlMethod.available) || (createMethod && !createMethod.available) ? (
        <div className="space-y-1 pt-1 border-t">
          {urlMethod && !urlMethod.available && (
            <p className="text-[11px] text-muted-foreground flex items-center gap-1">
              <FileText className="h-3 w-3 shrink-0" />Web clip: {urlMethod.reason}
            </p>
          )}
          {createMethod && !createMethod.available && (
            <p className="text-[11px] text-muted-foreground flex items-center gap-1">
              <FilePlus className="h-3 w-3 shrink-0" />Create markdown: {createMethod.reason}
            </p>
          )}
        </div>
      ) : null}
    </div>
  )
}
