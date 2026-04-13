import { useCallback, useEffect, useState } from "react"
import { useBuckets, type Bucket } from "@/hooks/use-buckets"
import { usePathCheck } from "@/hooks/use-path-check"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { relativeTime } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import {
  Database, Pencil, Plus, Trash2, FileText,
  Loader2, Clock, Infinity as InfinityIcon, RefreshCw, X, Check,
} from "lucide-react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { EmptyHero } from "@/components/ui/empty-hero"
import { BucketsSidebar } from "./buckets-sidebar"

// Color palette — must match _BUCKET_COLORS in backend router.py
const BUCKET_PALETTE = [
  "#6366f1", "#8b5cf6", "#ec4899", "#f97316",
  "#14b8a6", "#06b6d4", "#84cc16", "#f59e0b",
]

function BucketPathStatus({ path }: { path: string }) {
  const check = usePathCheck(path)
  if (check.status === "idle") return null
  if (check.status === "checking") return <p className="text-xs text-muted-foreground mt-1">Checking...</p>
  if (check.status === "ok") return <p className="text-xs text-green-600 dark:text-green-400 mt-1">Path found</p>
  if (check.status === "not_found") return <p className="text-xs text-destructive mt-1">Path not found</p>
  if (check.status === "needs_restart") {
    return (
      <p className="text-xs text-yellow-600 dark:text-yellow-400 mt-1">
        Path not mounted — creating this bucket will add the mount and prompt you to restart Docker.
      </p>
    )
  }
  if (check.status === "bad_mount") {
    return (
      <p className="text-xs text-destructive mt-1">
        Path configured but not accessible — check the host path exists and restart Docker.
      </p>
    )
  }
  return null
}

interface BucketFile {
  path: string
  title: string
  chunk_count: number
}

// -- Create form -------------------------------------------------------------

function BucketCreateForm({
  onCreated,
  onCancel,
  createBucket,
}: {
  onCreated: (id: string) => void
  onCancel: () => void
  createBucket: ReturnType<typeof useBuckets>["createBucket"]
}) {
  const [name, setName] = useState("")
  const [path, setPath] = useState("")
  const [glob, setGlob] = useState("**/*.md")
  const [expiresIn, setExpiresIn] = useState<number | null>(null)
  const [color, setColor] = useState<string | null>(null)

  async function handleCreate() {
    if (!name.trim() || !path.trim()) return
    const res = await createBucket({
      name: name.trim(),
      sources: [{ path: path.trim(), glob: glob.trim() || "**/*.md" }],
      expires_in: expiresIn,
      color: color ?? undefined,
    })
    if (res) {
      onCreated(res.id)
    }
  }

  return (
    <div className="p-6 max-w-xl">
      <h2 className="text-base font-semibold mb-4">New Bucket</h2>
      <div className="space-y-4">
        <div>
          <label className="text-sm font-medium">Name</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. grpc-evaluation"
            className="mt-1"
            autoFocus
          />
        </div>
        <div>
          <label className="text-sm font-medium">Source path</label>
          <Input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="Absolute path to file or directory"
            className="mt-1"
          />
          <BucketPathStatus path={path} />
        </div>
        <div>
          <label className="text-sm font-medium">Glob pattern</label>
          <Input
            value={glob}
            onChange={(e) => setGlob(e.target.value)}
            placeholder="**/*.md"
            className="mt-1"
          />
        </div>
        <div>
          <label className="text-sm font-medium">Expires in</label>
          <Select
            value={expiresIn === null ? "permanent" : String(expiresIn)}
            onValueChange={(v) => {
              if (v === "permanent") setExpiresIn(null)
              else setExpiresIn(Number(v))
            }}
          >
            <SelectTrigger className="mt-1">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="permanent">
                <span className="flex items-center gap-1.5"><InfinityIcon className="h-4 w-4" /> Permanent</span>
              </SelectItem>
              <SelectItem value="3600">
                <span className="flex items-center gap-1.5"><Clock className="h-4 w-4" /> 1 hour</span>
              </SelectItem>
              <SelectItem value="86400">
                <span className="flex items-center gap-1.5"><Clock className="h-4 w-4" /> 24 hours</span>
              </SelectItem>
              <SelectItem value="604800">
                <span className="flex items-center gap-1.5"><Clock className="h-4 w-4" /> 7 days</span>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-sm font-medium">Color</label>
          <div className="flex items-center gap-2 mt-1">
            {BUCKET_PALETTE.map((c) => (
              <button
                key={c}
                type="button"
                title={c}
                className="h-6 w-6 rounded-full border-2 transition-transform hover:scale-110"
                style={{
                  backgroundColor: c,
                  borderColor: color === c ? "hsl(var(--foreground))" : "transparent",
                }}
                onClick={() => setColor(color === c ? null : c)}
              />
            ))}
            <span className="text-xs text-muted-foreground ml-1">
              {color ? color : "auto-assigned"}
            </span>
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <Button
            size="sm"
            onClick={handleCreate}
            disabled={!name.trim() || !path.trim()}
          >
            Create
          </Button>
          <Button size="sm" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  )
}

// -- Edit form (inline in detail panel) -------------------------------------

function BucketEditForm({
  bucket,
  onSave,
  onCancel,
  updateBucket,
}: {
  bucket: Bucket
  onSave: () => void
  onCancel: () => void
  updateBucket: ReturnType<typeof useBuckets>["updateBucket"]
}) {
  const [name, setName] = useState(bucket.name)
  const [color, setColor] = useState<string | null>(bucket.color)
  const [expiresIn, setExpiresIn] = useState<number | null | "keep">("keep")

  async function handleSave() {
    const params: Parameters<typeof updateBucket>[1] = {}
    if (name.trim() && name.trim() !== bucket.name) params.name = name.trim()
    if (color !== bucket.color) params.color = color
    if (expiresIn !== "keep") params.expires_in = expiresIn
    if (Object.keys(params).length > 0) {
      await updateBucket(bucket.id, params)
    }
    onSave()
  }

  return (
    <Card className="mb-4">
      <CardContent className="pt-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Edit bucket</span>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onCancel}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
        <div>
          <label className="text-xs font-medium">Name</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 h-8 text-sm"
            autoFocus
          />
        </div>
        <div>
          <label className="text-xs font-medium">Expiration</label>
          <Select
            value={expiresIn === "keep" ? "keep" : expiresIn === null ? "permanent" : String(expiresIn)}
            onValueChange={(v) => {
              if (v === "keep") setExpiresIn("keep")
              else if (v === "permanent") setExpiresIn(null)
              else setExpiresIn(Number(v))
            }}
          >
            <SelectTrigger className="mt-1 h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="keep">
                <span className="text-muted-foreground">
                  {bucket.expires_at
                    ? `Keep: expires ${new Date(bucket.expires_at + "Z").toLocaleDateString()}`
                    : "Keep: permanent"}
                </span>
              </SelectItem>
              <SelectItem value="permanent">
                <span className="flex items-center gap-1.5"><InfinityIcon className="h-3.5 w-3.5" /> Make permanent</span>
              </SelectItem>
              <SelectItem value="3600">
                <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> 1 hour from now</span>
              </SelectItem>
              <SelectItem value="86400">
                <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> 24 hours from now</span>
              </SelectItem>
              <SelectItem value="604800">
                <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> 7 days from now</span>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-xs font-medium">Color</label>
          <div className="flex items-center gap-1.5 mt-1">
            {BUCKET_PALETTE.map((c) => (
              <button
                key={c}
                type="button"
                title={c}
                className="h-5 w-5 rounded-full border-2 transition-transform hover:scale-110"
                style={{
                  backgroundColor: c,
                  borderColor: (color ?? bucket.color) === c ? "hsl(var(--foreground))" : "transparent",
                }}
                onClick={() => setColor(color === c ? bucket.color : c)}
              />
            ))}
          </div>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={handleSave} className="gap-1">
            <Check className="h-3.5 w-3.5" /> Save
          </Button>
          <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
        </div>
      </CardContent>
    </Card>
  )
}

// -- Bucket detail panel ----------------------------------------------------

function BucketDetailPanel({
  bucket,
  onDelete,
  onViewFile,
  updateBucket,
  refresh,
}: {
  bucket: Bucket
  onDelete: (id: string) => void
  onViewFile: (path: string) => void
  updateBucket: ReturnType<typeof useBuckets>["updateBucket"]
  refresh: () => Promise<void>
}) {
  const [files, setFiles] = useState<BucketFile[]>([])
  const [loadingFiles, setLoadingFiles] = useState(false)
  const [filesIndexing, setFilesIndexing] = useState(false)
  const [editing, setEditing] = useState(false)
  const [reindexing, setReindexing] = useState(false)

  const loadFiles = useCallback(async () => {
    setLoadingFiles(true)
    try {
      const res = await api.get<{ files: BucketFile[]; indexing?: boolean }>(
        `/api/buckets/${bucket.id}/files`
      )
      setFiles(res.files)
      setFilesIndexing(res.indexing ?? false)
    } catch (err) {
      console.error("Failed to load bucket files", err)
    } finally {
      setLoadingFiles(false)
    }
  }, [bucket.id])

  useEffect(() => {
    loadFiles()
  }, [loadFiles])

  async function handleReindex() {
    setReindexing(true)
    const toastId = toast.loading(`Reindexing "${bucket.name}"...`)
    try {
      const res = await api.post<{ added_files: number; added_chunks: number }>(
        `/api/buckets/${bucket.id}/reindex`, {}
      )
      await refresh()
      toast.success(`Reindexed "${bucket.name}"`, {
        id: toastId,
        description: `${res.added_files} file${res.added_files !== 1 ? "s" : ""}, ${res.added_chunks} chunk${res.added_chunks !== 1 ? "s" : ""} added`,
        duration: 4000,
      })
      loadFiles()
    } catch (err) {
      toast.error(`Reindex failed: ${(err as Error).message}`, { id: toastId })
    } finally {
      setReindexing(false)
    }
  }

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
                style={{ backgroundColor: bucket.color ?? "#ff3333" }}
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

// -- Empty state -------------------------------------------------------------

function BucketsEmptyState({ onNewBucket }: { onNewBucket: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4">
      <EmptyHero icon={Database} label="Buckets" />
      <p className="text-sm text-muted-foreground text-center max-w-sm">
        Buckets are temporary document collections for focused analysis.
        Create one to load external docs, vendor APIs, or research material
        without mixing them into your permanent knowledge base.
      </p>
      <Button size="sm" className="gap-1.5" onClick={onNewBucket}>
        <Plus className="h-4 w-4" />
        New Bucket
      </Button>
    </div>
  )
}

// -- Main tab ----------------------------------------------------------------

export function BucketsTab() {
  const { buckets, createBucket, updateBucket, deleteBucket, refresh } = useBuckets()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [viewingPath, setViewingPath] = useState<string | null>(null)

  // Poll for updates — faster when any bucket is indexing
  const anyIndexing = buckets.some((b) => b.indexing)
  useEffect(() => {
    const interval = setInterval(refresh, anyIndexing ? 3000 : 15000)
    return () => clearInterval(interval)
  }, [refresh, anyIndexing])

  // If selected bucket was deleted, deselect it
  useEffect(() => {
    if (selectedId && !buckets.find((b) => b.id === selectedId)) {
      setSelectedId(null)
    }
  }, [buckets, selectedId])

  const selectedBucket = buckets.find((b) => b.id === selectedId) ?? null

  function handleSelectBucket(id: string) {
    setCreating(false)
    setSelectedId(id)
  }

  function handleNewBucket() {
    setSelectedId(null)
    setCreating(true)
  }

  async function handleDelete() {
    if (!confirmDelete) return
    await deleteBucket(confirmDelete)
    setConfirmDelete(null)
  }

  return (
    <div className="flex h-full overflow-hidden">
      <BucketsSidebar
        buckets={buckets}
        selectedId={creating ? null : selectedId}
        onSelect={handleSelectBucket}
        onNewBucket={handleNewBucket}
      />

      <div className="flex-1 min-w-0 overflow-hidden">
        {creating && (
          <BucketCreateForm
            createBucket={createBucket}
            onCreated={(id) => {
              setCreating(false)
              setSelectedId(id)
            }}
            onCancel={() => setCreating(false)}
          />
        )}

        {!creating && selectedBucket && (
          <BucketDetailPanel
            bucket={selectedBucket}
            onDelete={setConfirmDelete}
            onViewFile={(path) => setViewingPath(path)}
            updateBucket={updateBucket}
            refresh={refresh}
          />
        )}

        {!creating && !selectedBucket && (
          <BucketsEmptyState onNewBucket={handleNewBucket} />
        )}
      </div>

      <FileViewerDialog
        path={viewingPath}
        onClose={() => setViewingPath(null)}
      />

      <ConfirmDialog
        open={confirmDelete !== null}
        onOpenChange={(open) => { if (!open) setConfirmDelete(null) }}
        title="Delete bucket?"
        description={`This will permanently delete the bucket "${buckets.find((b) => b.id === confirmDelete)?.name}" and all its indexed content.`}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={handleDelete}
      />
    </div>
  )
}
