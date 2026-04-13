import { useCallback, useEffect, useState } from "react"
import { useBuckets, type Bucket } from "@/hooks/use-buckets"
import { usePathCheck } from "@/hooks/use-path-check"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { relativeTime } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { Database, Plus, Trash2, FileText, ChevronDown, ChevronRight, Loader2, Clock, Infinity as InfinityIcon, RefreshCw } from "lucide-react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { EmptyHero } from "@/components/ui/empty-hero"

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

function BucketCard({
  bucket,
  onDelete,
  onViewFile,
  onUpdateExpiration,
  onReindex,
}: {
  bucket: Bucket
  onDelete: (id: string) => void
  onViewFile: (path: string) => void
  onUpdateExpiration: (id: string, expiresIn: number | null) => Promise<void>
  onReindex: (id: string) => Promise<void>
}) {
  const [expanded, setExpanded] = useState(false)
  const [files, setFiles] = useState<BucketFile[]>([])
  const [loadingFiles, setLoadingFiles] = useState(false)
  const [reindexing, setReindexing] = useState(false)

  const [filesIndexing, setFilesIndexing] = useState(false)

  const loadFiles = useCallback(async () => {
    setLoadingFiles(true)
    try {
      const res = await api.get<{ files: BucketFile[]; indexing?: boolean }>(`/api/buckets/${bucket.id}/files`)
      setFiles(res.files)
      setFilesIndexing(res.indexing ?? false)
    } catch (err) {
      console.error("Failed to load bucket files for", bucket.id, err)
    } finally {
      setLoadingFiles(false)
    }
  }, [bucket.id])

  function handleToggle() {
    if (!expanded) loadFiles()
    setExpanded(!expanded)
  }

  const sources = (() => {
    try { return JSON.parse(bucket.sources) as { path: string; glob?: string }[] }
    catch (err) {
      console.error("Failed to parse bucket sources for", bucket.id, err)
      return []
    }
  })()

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="shrink-0 text-muted-foreground hover:text-foreground"
            onClick={handleToggle}
          >
            {expanded
              ? <ChevronDown className="h-4 w-4" />
              : <ChevronRight className="h-4 w-4" />
            }
          </button>
          <div className="flex-1 min-w-0">
            <CardTitle className="text-sm flex items-center gap-2">
              <Database className="h-4 w-4 shrink-0" />
              {bucket.name}
            </CardTitle>
            <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
              <span>{bucket.file_count} files</span>
              <span>{bucket.chunk_count} chunks</span>
              <span>{relativeTime(bucket.created_at)}</span>
              {bucket.indexing && (
                <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-500/50 gap-1">
                  <Loader2 className="h-2.5 w-2.5 animate-spin" />
                  indexing
                </Badge>
              )}
              {bucket.expires_at ? (
                <Badge variant="outline" className="text-[10px]">
                  expires {new Date(bucket.expires_at + "Z").toLocaleDateString()}
                </Badge>
              ) : (
                <Badge variant="secondary" className="text-[10px]">permanent</Badge>
              )}
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground shrink-0"
            disabled={reindexing}
            title="Reindex from sources"
            onClick={async () => {
              setReindexing(true)
              await onReindex(bucket.id)
              setReindexing(false)
              loadFiles()
            }}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${reindexing ? "animate-spin" : ""}`} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-destructive shrink-0"
            onClick={() => onDelete(bucket.id)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardHeader>
      {expanded && (
        <CardContent className="pt-0">
          {/* Sources */}
          <div className="mb-3">
            <p className="text-xs text-muted-foreground font-medium mb-1">Sources</p>
            <div className="space-y-0.5">
              {sources.map((s, i) => (
                <p key={i} className="text-xs text-muted-foreground font-mono truncate">
                  {s.path} <span className="text-muted-foreground/60">{s.glob || "**/*.md"}</span>
                </p>
              ))}
            </div>
          </div>

          {/* Expiration */}
          <div className="mb-3">
            <p className="text-xs text-muted-foreground font-medium mb-1">Change expiration</p>
            <div className="flex items-center gap-2">
              <Select
                value="__pick__"
                onValueChange={async (v) => {
                  if (v === "permanent") await onUpdateExpiration(bucket.id, null)
                  else if (v === "1h") await onUpdateExpiration(bucket.id, 3600)
                  else if (v === "24h") await onUpdateExpiration(bucket.id, 86400)
                  else if (v === "7d") await onUpdateExpiration(bucket.id, 604800)
                }}
              >
                <SelectTrigger className="h-7 text-xs w-44">
                  <SelectValue placeholder={bucket.expires_at ? `Expires: ${new Date(bucket.expires_at + "Z").toLocaleDateString()}` : "Permanent"} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__pick__" disabled className="text-muted-foreground">
                    {bucket.expires_at ? `Current: ${new Date(bucket.expires_at + "Z").toLocaleDateString()}` : "Currently permanent"}
                  </SelectItem>
                  <SelectItem value="permanent">
                    <span className="flex items-center gap-1"><InfinityIcon className="h-3 w-3" /> Make permanent</span>
                  </SelectItem>
                  <SelectItem value="1h">
                    <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> 1 hour from now</span>
                  </SelectItem>
                  <SelectItem value="24h">
                    <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> 24 hours from now</span>
                  </SelectItem>
                  <SelectItem value="7d">
                    <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> 7 days from now</span>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Files */}
          {loadingFiles && (
            <div className="flex items-center gap-2 py-4 justify-center text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading files...
            </div>
          )}
          {!loadingFiles && files.length > 0 && (
            <div className="space-y-0.5">
              <div className="flex items-center gap-2 mb-1">
                <p className="text-xs text-muted-foreground font-medium">
                  Files ({files.length})
                </p>
                {filesIndexing && (
                  <span className="text-[10px] text-amber-600 flex items-center gap-1">
                    <Loader2 className="h-2.5 w-2.5 animate-spin" />
                    Embedding in progress — search available when complete
                  </span>
                )}
              </div>
              <ScrollArea style={{ height: Math.min(files.length * 32, 320) }}>
                {files.map((f) => (
                  <button
                    key={f.path}
                    type="button"
                    className="flex items-center gap-2 w-full text-left px-2 py-1.5 rounded hover:bg-accent text-xs"
                    onClick={() => onViewFile(f.path)}
                  >
                    <FileText className="h-3 w-3 text-muted-foreground shrink-0" />
                    <span className="truncate flex-1 min-w-0">
                      {f.title || f.path.split("/").pop()}
                    </span>
                    <span className="text-muted-foreground shrink-0">
                      {f.chunk_count} chunks
                    </span>
                  </button>
                ))}
              </ScrollArea>
            </div>
          )}
          {!loadingFiles && files.length === 0 && !loadingFiles && (
            <p className="text-xs text-muted-foreground text-center py-2">
              No files in this bucket
            </p>
          )}
        </CardContent>
      )}
    </Card>
  )
}

export function BucketsTab() {
  const { buckets, createBucket, deleteBucket, updateExpiration, refresh } = useBuckets()
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [viewingPath, setViewingPath] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState("")
  const [newPath, setNewPath] = useState("")
  const [newGlob, setNewGlob] = useState("**/*.md")
  const [newExpiresInSecs, setNewExpiresInSecs] = useState<number | null>(null)

  // Poll for bucket updates — faster when any bucket is indexing
  const anyIndexing = buckets.some((b) => b.indexing)
  useEffect(() => {
    const interval = setInterval(refresh, anyIndexing ? 3000 : 15000)
    return () => clearInterval(interval)
  }, [refresh, anyIndexing])

  async function handleCreate() {
    if (!newName.trim() || !newPath.trim()) return
    setCreating(false)
    const params: Parameters<typeof createBucket>[0] = {
      name: newName.trim(),
      sources: [{ path: newPath.trim(), glob: newGlob.trim() || "**/*.md" }],
    }
    if (newExpiresInSecs && newExpiresInSecs > 0) {
      params.expires_in = newExpiresInSecs
    }
    await createBucket(params)
    setNewName("")
    setNewPath("")
    setNewGlob("**/*.md")
    setNewExpiresInSecs(null)
  }

  async function handleReindex(id: string) {
    const name = buckets.find((b) => b.id === id)?.name
    const toastId = toast.loading(`Reindexing "${name}"...`)
    try {
      const res = await api.post<{ added_files: number; added_chunks: number }>(`/api/buckets/${id}/reindex`, {})
      await refresh()
      toast.success(`Reindexed "${name}"`, {
        id: toastId,
        description: `${res.added_files} file${res.added_files !== 1 ? "s" : ""}, ${res.added_chunks} chunk${res.added_chunks !== 1 ? "s" : ""} added`,
        duration: 4000,
      })
    } catch (err) {
      toast.error(`Reindex failed: ${(err as Error).message}`, { id: toastId })
    }
  }

  async function handleDelete() {
    if (!confirmDelete) return
    await deleteBucket(confirmDelete)
    setConfirmDelete(null)
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-4 space-y-4 max-w-4xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Buckets</h2>
              <p className="text-sm text-muted-foreground">
                Temporary document collections with isolated search and chat.
              </p>
            </div>
            <Button
              size="sm"
              className="gap-1.5"
              onClick={() => setCreating(!creating)}
            >
              <Plus className="h-4 w-4" />
              New Bucket
            </Button>
          </div>

          {/* Create form */}
          {creating && (
            <Card>
              <CardContent className="pt-4 space-y-3">
                <div>
                  <label className="text-sm font-medium">Name</label>
                  <Input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="e.g. grpc-evaluation"
                    className="mt-1"
                    autoFocus
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Source path</label>
                  <Input
                    value={newPath}
                    onChange={(e) => setNewPath(e.target.value)}
                    placeholder="Absolute path to file or directory"
                    className="mt-1"
                  />
                  <BucketPathStatus path={newPath} />
                </div>
                <div>
                  <label className="text-sm font-medium">Glob pattern</label>
                  <Input
                    value={newGlob}
                    onChange={(e) => setNewGlob(e.target.value)}
                    placeholder="**/*.md"
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Expires in</label>
                  <Select
                    value={newExpiresInSecs === null ? "permanent" : newExpiresInSecs === 3600 ? "1h" : newExpiresInSecs === 86400 ? "24h" : newExpiresInSecs === 604800 ? "7d" : ""}
                    onValueChange={(v) => {
                      if (v === "permanent") setNewExpiresInSecs(null)
                      else if (v === "1h") setNewExpiresInSecs(3600)
                      else if (v === "24h") setNewExpiresInSecs(86400)
                      else if (v === "7d") setNewExpiresInSecs(604800)
                    }}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="Permanent" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="permanent">
                        <span className="flex items-center gap-1"><InfinityIcon className="h-4 w-4" /> Permanent</span>
                      </SelectItem>
                      <SelectItem value="1h">
                        <span className="flex items-center gap-1"><Clock className="h-4 w-4" /> 1 hour</span>
                      </SelectItem>
                      <SelectItem value="24h">
                        <span className="flex items-center gap-1"><Clock className="h-4 w-4" /> 24 hours</span>
                      </SelectItem>
                      <SelectItem value="7d">
                        <span className="flex items-center gap-1"><Clock className="h-4 w-4" /> 7 days</span>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={handleCreate}
                    disabled={!newName.trim() || !newPath.trim()}
                  >
                    Create
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setCreating(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Empty state */}
          {buckets.length === 0 && !creating && (
            <div className="flex flex-col items-center justify-center py-20 gap-4">
              <EmptyHero icon={Database} label="Buckets" />
              <p className="text-sm text-muted-foreground text-center max-w-md">
                Buckets are temporary document collections for focused analysis.
                Create one to load external docs, vendor APIs, or research material
                without mixing them into your permanent knowledge base.
              </p>
            </div>
          )}

          {/* Bucket list */}
          {buckets.map((bucket) => (
            <BucketCard
              key={bucket.id}
              bucket={bucket}
              onDelete={setConfirmDelete}
              onViewFile={setViewingPath}
              onUpdateExpiration={updateExpiration}
              onReindex={handleReindex}
            />
          ))}
        </div>
      </ScrollArea>

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
