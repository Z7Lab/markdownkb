import { useCallback, useState } from "react"
import { type Bucket, type useBuckets, useBucketFiles } from "@/hooks/use-buckets"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { relativeTime, slugifyFilename } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, SortableTableHead } from "@/components/ui/table"
import {
  Pencil, Trash2, FileText, Loader2, Clock, Check, X as XIcon,
  Infinity as InfinityIcon, RefreshCw, Download, FolderInput, MessageSquare, Github, FilePlus,
  EyeOff, Eye,
} from "lucide-react"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { BucketEditForm } from "./bucket-edit-form"
import { BucketPathStatus } from "./bucket-path-status"
import { BucketChatDrawer } from "./bucket-chat-drawer"
import { GithubImportDialog } from "./github-import-dialog"
import { IngestionPanel } from "@/components/import/ingestion-panel"
import { CreateMarkdownDialog } from "@/components/import/create-markdown-dialog"
import { useImportCapabilities } from "@/hooks/use-import-capabilities"

export interface BucketDetailPanelProps {
  bucket: Bucket
  onDelete: (id: string) => void
  onViewFile: (path: string) => void
  updateBucket: ReturnType<typeof useBuckets>["updateBucket"]
  exportBucket: ReturnType<typeof useBuckets>["exportBucket"]
  promoteBucket: ReturnType<typeof useBuckets>["promoteBucket"]
  setBucketHidden: ReturnType<typeof useBuckets>["setBucketHidden"]
  refresh: () => Promise<void>
}

export function BucketDetailPanel({
  bucket,
  onDelete,
  onViewFile,
  updateBucket,
  exportBucket,
  promoteBucket,
  setBucketHidden,
  refresh,
}: BucketDetailPanelProps) {
  const { files, loading: loadingFiles, indexing: filesIndexing, reload: reloadFiles } = useBucketFiles(bucket.id)
  const [editing, setEditing] = useState(false)
  const [reindexing, setReindexing] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [renamingPath, setRenamingPath] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState("")
  const [renaming, setRenaming] = useState(false)
  const [sortKey, setSortKey] = useState<"path" | "chunk_count" | "indexed_at">("path")
  const [deletingPath, setDeletingPath] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc")

  function handleSort(key: string) {
    const k = key as "path" | "chunk_count" | "indexed_at"
    if (sortKey === k) setSortDir((d) => d === "asc" ? "desc" : "asc")
    else { setSortKey(k); setSortDir(k === "indexed_at" ? "desc" : "asc") }
  }

  // Import state
  const [githubOpen, setGithubOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const { find: findCapability } = useImportCapabilities()
  const createAvailable = !!findCapability("create_markdown")?.available

  const batchPushDocuments = useCallback(async (docs: { name: string; content: string }[]) => {
    await api.post(`/api/v1/buckets/${bucket.id}/documents`, {
      documents: docs,
      async_embed: true,
    })
  }, [bucket.id])

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

  const startRename = useCallback((path: string, currentDisplay: string) => {
    const name = currentDisplay.endsWith(".md") ? currentDisplay.slice(0, -3) : currentDisplay
    setRenamingPath(path)
    setRenameValue(name)
  }, [])

  const commitRename = useCallback(async () => {
    if (!renamingPath || !renameValue.trim() || renaming) return
    setRenaming(true)
    try {
      const slugged = slugifyFilename(renameValue)
      if (!slugged) { setRenaming(false); return }
      await api.patch(`/api/v1/buckets/${bucket.id}/documents`, {
        old_path: renamingPath,
        new_name: slugged,
      })
      setRenamingPath(null)
      setRenameValue("")
      reloadFiles()
      toast.success("Document renamed")
    } catch (err) {
      toast.error(`Rename failed: ${(err as Error).message}`)
    } finally {
      setRenaming(false)
    }
  }, [renamingPath, renameValue, renaming, bucket.id, reloadFiles])

  const cancelRename = useCallback(() => {
    setRenamingPath(null)
    setRenameValue("")
  }, [])

  const handleDeleteDocument = useCallback(async (path: string) => {
    setDeletingPath(path)
    try {
      await api.del(`/api/v1/buckets/${bucket.id}/documents?path=${encodeURIComponent(path)}`)
      reloadFiles()
      toast.success("Document deleted")
    } catch (err) {
      toast.error(`Delete failed: ${(err as Error).message}`)
    } finally {
      setDeletingPath(null)
    }
  }, [bucket.id, reloadFiles])

  const handleScopeToggle = useCallback(async (path: string, allPaths: string[]) => {
    const current = (bucket.scope_paths && bucket.scope_paths.length > 0) ? bucket.scope_paths : allPaths
    const next = current.includes(path)
      ? current.filter((p) => p !== path)
      : [...current, path]
    const newScope = next.length === allPaths.length ? null : next
    try {
      await api.patch(`/api/v1/buckets/${bucket.id}`, { scope_paths: newScope })
      await refresh()
    } catch (err) {
      toast.error(`Failed to update scope: ${(err as Error).message}`)
    }
  }, [bucket.id, bucket.scope_paths, refresh])

  const sources = (() => {
    try { return JSON.parse(bucket.sources) as { path: string; glob?: string }[] }
    catch (err) {
      console.warn(`Malformed sources JSON for bucket "${bucket.name}"; treating as empty.`, err)
      return []
    }
  })()

  return (
    <>
    <div className="flex flex-col h-full overflow-hidden">
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-6 space-y-4">
          {/* Header */}
          <div className="space-y-2">
            {/* Name row */}
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="h-3 w-3 rounded-full shrink-0"
                style={{ backgroundColor: bucket.color ?? "var(--bucket-default)" }}
              />
              <h2 className="text-lg font-semibold flex items-center gap-2 min-w-0 truncate">
                {bucket.name}
                {bucket.indexing && (
                  <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-500/50 gap-1 shrink-0">
                    <Loader2 className="h-2.5 w-2.5 animate-spin" />
                    indexing
                  </Badge>
                )}
                {bucket.expired && (
                  <Badge variant="outline" className="text-[10px] text-destructive border-destructive/40 shrink-0">
                    expired
                  </Badge>
                )}
                {bucket.hidden && (
                  <Badge variant="outline" className="text-[10px] text-muted-foreground shrink-0">
                    hidden
                  </Badge>
                )}
              </h2>
              {!bucket.expired && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0 text-muted-foreground hover:text-foreground"
                  onClick={() => setChatOpen(true)}
                  aria-label="Chat with bucket"
                  title="Chat with this bucket"
                >
                  <MessageSquare className="h-4 w-4" />
                </Button>
              )}
            </div>

            {/* Stats + action toolbar */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-3 text-xs text-muted-foreground min-w-0">
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
              <div className="flex items-center gap-0.5 shrink-0">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  aria-label="Edit bucket"
                  title="Edit bucket"
                  onClick={() => setEditing(!editing)}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  aria-label="Reindex from sources"
                  title="Reindex from sources"
                  disabled={reindexing}
                  onClick={handleReindex}
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${reindexing ? "animate-spin" : ""}`} />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  aria-label="Export bucket"
                  title="Export bucket as zip"
                  onClick={() => exportBucket(bucket.id, bucket.name)}
                >
                  <Download className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  aria-label="Promote to watched directories"
                  title="Add bucket sources to watched directories"
                  onClick={() => promoteBucket(bucket.id, bucket.name)}
                >
                  <FolderInput className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  aria-label={bucket.hidden ? "Restore bucket" : "Hide bucket"}
                  title={bucket.hidden ? "Restore to lists and selectors" : "Hide from lists and selectors"}
                  onClick={() => setBucketHidden(bucket.id, !bucket.hidden)}
                >
                  {bucket.hidden ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-destructive"
                  aria-label="Delete bucket"
                  title="Delete bucket"
                  onClick={() => onDelete(bucket.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </div>

          {/* Description */}
          {bucket.description && !editing && (
            <p className="text-sm text-muted-foreground">{bucket.description}</p>
          )}

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
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">Sources</p>
            {sources.length > 0 ? (
              <div className="space-y-1">
                {sources.map((s, i) => (
                  <div key={i}>
                    <p className="text-xs font-mono text-muted-foreground truncate">
                      {s.path}
                      {s.glob && s.glob !== "**/*.md" && (
                        <span className="text-muted-foreground/60 ml-2">{s.glob}</span>
                      )}
                    </p>
                    <BucketPathStatus path={s.path} context="view" />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">No local sources — add content via upload or URL clip.</p>
            )}
          </div>

          {/* Add content */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-muted-foreground">Add content</p>
              <div className="flex items-center gap-1.5">
                {createAvailable && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 gap-1.5"
                    onClick={() => setCreateOpen(true)}
                    title="Write a new markdown note into this bucket"
                  >
                    <FilePlus className="h-3.5 w-3.5" />
                    New note
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 gap-1.5"
                  onClick={() => setGithubOpen(true)}
                  title="Import .md/.mdx files from a GitHub repository"
                >
                  <Github className="h-3.5 w-3.5" />
                  GitHub
                </Button>
              </div>
            </div>
            <IngestionPanel
              destination={{ type: "bucket", id: bucket.id }}
              onIngested={reloadFiles}
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

            {!loadingFiles && files.length > 0 && (() => {
              const sortedFiles = [...files].sort((a, b) => {
                let cmp = 0
                if (sortKey === "path") cmp = (a.title || a.path).localeCompare(b.title || b.path)
                else if (sortKey === "chunk_count") cmp = a.chunk_count - b.chunk_count
                else cmp = (a.indexed_at ?? "").localeCompare(b.indexed_at ?? "")
                return sortDir === "asc" ? cmp : -cmp
              })
              return (
              <div className="border rounded-md overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <SortableTableHead sortKey="path" activeSortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="text-xs h-8 px-3">File</SortableTableHead>
                      <SortableTableHead sortKey="chunk_count" activeSortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="text-xs h-8 px-3">Chunks</SortableTableHead>
                      <SortableTableHead sortKey="indexed_at" activeSortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="text-xs h-8 px-3">Last indexed</SortableTableHead>
                      <TableHead className="text-xs h-8 px-3">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="cursor-default">Scope</span>
                          </TooltipTrigger>
                          <TooltipContent>Include in retrieval scope — only checked files are searched when this bucket is active</TooltipContent>
                        </Tooltip>
                      </TableHead>
                      <TableHead className="h-8 w-6 px-3">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sortedFiles.map((f) => {
                      const allPaths = files.map((x) => x.path)
                      const isVirtual = f.path.startsWith("bucket://")
                      const display = f.title || f.path.split("/").pop() || f.path
                      const isRenaming = renamingPath === f.path
                      const inScope = !bucket.scope_paths || bucket.scope_paths.includes(f.path)
                      return (
                        <TableRow key={f.path} className="text-xs">
                          {isRenaming ? (
                            <TableCell colSpan={5} className="px-3 py-1.5">
                              <div className="flex items-center gap-1 min-w-0">
                                <Input
                                  value={renameValue}
                                  onChange={(e) => setRenameValue(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") void commitRename()
                                    if (e.key === "Escape") cancelRename()
                                  }}
                                  className="h-6 text-xs flex-1"
                                  autoFocus
                                  disabled={renaming}
                                />
                                <span className="text-[10px] text-muted-foreground">.md</span>
                                <button
                                  className="p-0.5 hover:text-green-600 disabled:opacity-50"
                                  onClick={() => void commitRename()}
                                  disabled={renaming || !renameValue.trim()}
                                  aria-label="Confirm rename"
                                >
                                  {renaming ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                                </button>
                                <button
                                  className="p-0.5 hover:text-destructive"
                                  onClick={cancelRename}
                                  disabled={renaming}
                                  aria-label="Cancel rename"
                                >
                                  <XIcon className="h-3 w-3" />
                                </button>
                              </div>
                            </TableCell>
                          ) : (
                            <>
                              <TableCell className="px-3 py-1.5">
                                <button
                                  type="button"
                                  className="flex items-center gap-2 min-w-0 text-left w-full"
                                  onClick={() => onViewFile(f.path)}
                                >
                                  <FileText className="h-3 w-3 text-muted-foreground shrink-0" />
                                  <span className="truncate">{display}</span>
                                </button>
                              </TableCell>
                              <TableCell className="px-3 py-1.5 text-muted-foreground tabular-nums">{f.chunk_count}</TableCell>
                              <TableCell className="px-3 py-1.5 text-muted-foreground whitespace-nowrap">
                                {f.indexed_at ? relativeTime(f.indexed_at) : "—"}
                              </TableCell>
                              <TableCell className="px-3 py-1.5">
                                <input
                                  type="checkbox"
                                  className="cursor-pointer"
                                  checked={inScope}
                                  onChange={() => void handleScopeToggle(f.path, allPaths)}
                                  aria-label={`${inScope ? "Remove from" : "Add to"} scope`}
                                  onClick={(e) => e.stopPropagation()}
                                />
                              </TableCell>
                              <TableCell className="px-3 py-1.5">
                                <div className="flex items-center gap-1">
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <button
                                        type="button"
                                        className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed"
                                        onClick={() => isVirtual && startRename(f.path, display)}
                                        disabled={!isVirtual}
                                        aria-label={isVirtual ? "Rename document" : "Edit the file on disk and reindex to rename it"}
                                      >
                                        <Pencil className="h-3 w-3" />
                                      </button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                      {isVirtual ? "Rename document" : "Edit the file on disk and reindex to rename it"}
                                    </TooltipContent>
                                  </Tooltip>
                                  {isVirtual && (
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <button
                                          type="button"
                                          className="p-0.5 text-muted-foreground hover:text-destructive disabled:opacity-30 disabled:cursor-not-allowed"
                                          onClick={() => void handleDeleteDocument(f.path)}
                                          disabled={deletingPath === f.path}
                                          aria-label="Delete document"
                                        >
                                          {deletingPath === f.path
                                            ? <Loader2 className="h-3 w-3 animate-spin" />
                                            : <Trash2 className="h-3 w-3" />}
                                        </button>
                                      </TooltipTrigger>
                                      <TooltipContent>Delete document</TooltipContent>
                                    </Tooltip>
                                  )}
                                </div>
                              </TableCell>
                            </>
                          )}
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </div>
              )
            })()}
          </div>
        </div>
      </ScrollArea>

    </div>
    <BucketChatDrawer
      open={chatOpen}
      onClose={() => setChatOpen(false)}
      bucketId={bucket.id}
      bucketName={bucket.name}
    />
    <GithubImportDialog
      open={githubOpen}
      onClose={() => setGithubOpen(false)}
      onBatchImport={batchPushDocuments}
      onDone={reloadFiles}
    />
    <CreateMarkdownDialog
      open={createOpen}
      destination={{ type: "bucket", id: bucket.id }}
      onClose={() => setCreateOpen(false)}
      onCreated={reloadFiles}
    />
    </>
  )
}
