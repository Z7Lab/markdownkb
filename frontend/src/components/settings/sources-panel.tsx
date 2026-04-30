import React, { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { useIndexEvents } from "@/hooks/use-index-events"
import { usePathCheck } from "@/hooks/use-path-check"
import { api } from "@/lib/api"
import type { ProjectRoot, SourceConfig, VersioningStatus } from "@/lib/types"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import {
  CheckCircle2,
  AlertCircle,
  Loader2,
  Trash2,
  FileText,
  Pencil,
  Plus,
  X,
  FolderGit2,
  GitBranch,
  HardDrive,
  ShieldAlert,
} from "lucide-react"
import { toast } from "sonner"
import { VersioningSourceRow } from "./versioning-source-row"

function formatSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`
  return `${(n / 1024 ** 3).toFixed(2)} GB`
}

function AddDirectoryForm({ onSubmit }: { onSubmit: (path: string) => void }) {
  const [path, setPath] = useState("")

  function handleSubmit() {
    const v = path.trim()
    if (!v) return
    onSubmit(v)
    setPath("")
  }

  return (
    <div className="pt-2">
      <div className="flex gap-2">
        <Input
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="/path/to/documents"
          aria-label="Source path"
          className="flex-1"
          onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
        />
        <Button onClick={handleSubmit} disabled={!path.trim()}>
          Add
        </Button>
      </div>
      <PathStatus path={path} />
    </div>
  )
}

function PathBadge({ path }: { path: string }) {
  const check = usePathCheck(path, 0)

  let icon: React.ReactNode
  let message: string

  if (check.status === "idle" || check.status === "checking") {
    icon = <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
    message = "Checking..."
  } else if (check.status === "ok") {
    icon = <CheckCircle2 className="h-3.5 w-3.5 text-success" />
    message = "Accessible"
  } else if (check.status === "needs_restart") {
    icon = <AlertCircle className="h-3.5 w-3.5 text-yellow-500" />
    message = "Not mounted — restart container to apply"
  } else if (check.status === "bad_mount") {
    icon = <AlertCircle className="h-3.5 w-3.5 text-destructive" />
    message = "Configured but not accessible — check host path and restart"
  } else {
    icon = <AlertCircle className="h-3.5 w-3.5 text-destructive" />
    message = "Path not found"
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="shrink-0 cursor-default">{icon}</span>
      </TooltipTrigger>
      <TooltipContent>
        <p className="text-xs">{message}</p>
      </TooltipContent>
    </Tooltip>
  )
}

function PathStatus({ path }: { path: string }) {
  const check = usePathCheck(path)

  if (check.status === "idle" || check.status === "checking") {
    return check.status === "checking" ? <p className="text-xs text-muted-foreground mt-1">Checking...</p> : null
  }
  if (check.status === "ok") {
    return <p className="text-xs text-green-600 dark:text-green-400 mt-1">Path found</p>
  }
  if (check.status === "not_found") {
    return <p className="text-xs text-destructive mt-1">Path not found</p>
  }
  if (check.status === "needs_restart") {
    return (
      <p className="text-xs text-yellow-600 dark:text-yellow-400 mt-1">
        Not mounted yet — will be available after saving and restarting the container
      </p>
    )
  }
  if (check.status === "bad_mount") {
    return (
      <p className="text-xs text-destructive mt-1">
        Configured in compose.override.yml but not accessible — check that the host path exists, then restart the
        container
      </p>
    )
  }
  return null
}

function ProjectRootForm({
  initial,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  initial?: ProjectRoot
  onSubmit: (path: string, include: string[], exclude: string[], title?: string) => void
  onCancel: () => void
  submitLabel: string
}) {
  const [path, setPath] = useState(initial?.path ?? "")
  const [title, setTitle] = useState(initial?.title ?? "")
  const [includeInput, setIncludeInput] = useState("")
  const [excludeInput, setExcludeInput] = useState("")
  const [include, setInclude] = useState<string[]>(initial?.include ?? ["*.md", "docs/**/*.md"])
  const [exclude, setExclude] = useState<string[]>(initial?.exclude ?? [])

  function addInclude() {
    const v = includeInput.trim()
    if (v && !include.includes(v)) {
      setInclude([...include, v])
      setIncludeInput("")
    }
  }

  function addExclude() {
    const v = excludeInput.trim()
    if (v && !exclude.includes(v)) {
      setExclude([...exclude, v])
      setExcludeInput("")
    }
  }

  const canSubmit = path.trim() && include.length > 0

  return (
    <div className="space-y-3 rounded-md border p-3">
      {!initial && (
        <div>
          <Input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="/home/user/projects"
            onKeyDown={(e) =>
              e.key === "Enter" && canSubmit && onSubmit(path.trim(), include, exclude, title.trim() || undefined)
            }
          />
          <PathStatus path={path} />
        </div>
      )}
      <Input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Display name (optional, e.g. Work Projects)"
        className="h-8 text-xs"
        aria-label="Project root display name"
      />

      <div>
        <p className="text-xs text-muted-foreground mb-1.5">Include patterns</p>
        <div className="flex flex-wrap gap-1.5 mb-1.5">
          {include.map((p) => (
            <Badge key={p} variant="secondary" className="gap-1 font-mono text-xs">
              {p}
              <button onClick={() => setInclude(include.filter((i) => i !== p))} className="ml-0.5">
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
        <div className="flex gap-2">
          <Input
            value={includeInput}
            onChange={(e) => setIncludeInput(e.target.value)}
            placeholder="docs/**/*.md"
            aria-label="Include pattern"
            className="flex-1 h-8 text-xs"
            onKeyDown={(e) => e.key === "Enter" && addInclude()}
          />
          <Button variant="outline" size="sm" onClick={addInclude} disabled={!includeInput.trim()}>
            <Plus className="h-3 w-3" />
          </Button>
        </div>
      </div>

      <div>
        <p className="text-xs text-muted-foreground mb-1.5">Exclude patterns</p>
        <div className="flex flex-wrap gap-1.5 mb-1.5">
          {exclude.map((p) => (
            <Badge key={p} variant="outline" className="gap-1 font-mono text-xs">
              {p}
              <button onClick={() => setExclude(exclude.filter((e) => e !== p))} className="ml-0.5">
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
          {exclude.length === 0 && <span className="text-xs text-muted-foreground italic">None</span>}
        </div>
        <div className="flex gap-2">
          <Input
            value={excludeInput}
            onChange={(e) => setExcludeInput(e.target.value)}
            placeholder="CHANGELOG.md"
            aria-label="Exclude pattern"
            className="flex-1 h-8 text-xs"
            onKeyDown={(e) => e.key === "Enter" && addExclude()}
          />
          <Button variant="outline" size="sm" onClick={addExclude} disabled={!excludeInput.trim()}>
            <Plus className="h-3 w-3" />
          </Button>
        </div>
      </div>

      <div className="flex gap-2 justify-end pt-1">
        <Button variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          size="sm"
          onClick={() => onSubmit(path.trim(), include, exclude, title.trim() || undefined)}
          disabled={!canSubmit}
        >
          {submitLabel}
        </Button>
      </div>
    </div>
  )
}

export function SourcesPanel({
  sources,
  sourceConfigs,
  ignorePatterns,
  projectRoots,
  coreVersioningEnabled,
  onAdd,
  onRemove,
  onAddIgnore,
  onRemoveIgnore,
  onAddProjectRoot,
  onRemoveProjectRoot,
  onUpdateProjectRoot,
  onReloadSettings,
}: {
  sources: string[]
  sourceConfigs: SourceConfig[]
  ignorePatterns: string[]
  projectRoots: ProjectRoot[]
  coreVersioningEnabled: boolean
  onAdd: (path: string) => Promise<void>
  onRemove: (path: string, cleanup: boolean) => Promise<void>
  onAddIgnore: (pattern: string) => Promise<void>
  onRemoveIgnore: (pattern: string) => Promise<void>
  onAddProjectRoot: (
    path: string,
    include: string[],
    exclude: string[],
    title?: string,
  ) => Promise<{ docker_restart_required?: boolean; path_not_found?: boolean } | void>
  onRemoveProjectRoot: (path: string, cleanup: boolean) => Promise<void>
  onUpdateProjectRoot: (path: string, include: string[], exclude: string[], title?: string) => Promise<void>
  onReloadSettings: () => Promise<boolean> | void
}) {
  const [newPattern, setNewPattern] = useState("")
  const [pendingRemove, setPendingRemove] = useState<string | null>(null)
  const [pendingRemoveRoot, setPendingRemoveRoot] = useState<string | null>(null)
  const [showAddRoot, setShowAddRoot] = useState(false)
  const [editingRoot, setEditingRoot] = useState<string | null>(null)
  const [stats, setStats] = useState<{
    files_tracked: number
    files_complete: number
    files_error: number
    chunks_indexed: number
  } | null>(null)
  const [staleIgnored, setStaleIgnored] = useState<{ count: number } | null>(null)
  const [purgingStale, setPurgingStale] = useState(false)
  const { isIndexing, lastIndexedAt } = useIndexEvents()
  const [vstatus, setVStatus] = useState<VersioningStatus | null>(null)

  const reloadVersioningStatus = useCallback(() => {
    api
      .get<VersioningStatus>("/api/v1/versioning/status")
      .then(setVStatus)
      .catch(() => {
        /* status is non-critical UI data */
      })
  }, [])

  useEffect(() => {
    api
      .get<{
        files_tracked: number
        files_complete: number
        files_error: number
        chunks_indexed: number
      }>("/api/v1/stats")
      .then(setStats)
      .catch(() => {
        /* stats are non-critical UI data */
      })
    api
      .get<{ count: number }>("/api/v1/files/stale-ignored")
      .then(setStaleIgnored)
      .catch(() => {
        /* non-critical */
      })
  }, [lastIndexedAt])

  useEffect(() => {
    reloadVersioningStatus()
  }, [reloadVersioningStatus, sourceConfigs, coreVersioningEnabled])

  async function handleAddPattern() {
    if (!newPattern.trim()) return
    await onAddIgnore(newPattern.trim())
    setNewPattern("")
    api
      .get<{ count: number }>("/api/v1/files/stale-ignored")
      .then(setStaleIgnored)
      .catch(() => {}) /* best-effort */
  }

  async function handlePurgeStale() {
    setPurgingStale(true)
    try {
      const result = await api.del<{ purged: number }>("/api/v1/files/stale-ignored")
      toast.success(`Purged ${result.purged} stale file${result.purged !== 1 ? "s" : ""} from the index`)
      setStaleIgnored({ count: 0 })
    } catch {
      toast.error("Failed to purge stale files")
    } finally {
      setPurgingStale(false)
    }
  }

  return (
    <div className="space-y-4">
      {stats && (
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-6 text-sm">
              <div className="flex items-center gap-1.5">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{stats.files_tracked}</span>
                <span className="text-muted-foreground">files</span>
              </div>
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4 text-success" />
                <span className="font-medium">{stats.files_complete}</span>
                <span className="text-muted-foreground">indexed</span>
              </div>
              {stats.files_error > 0 && (
                <div className="flex items-center gap-1.5">
                  <AlertCircle className="h-4 w-4 text-error" />
                  <span className="font-medium text-error">{stats.files_error}</span>
                  <span className="text-muted-foreground">errors</span>
                </div>
              )}
              <div className="flex items-center gap-1.5">
                <span className="font-medium">{stats.chunks_indexed}</span>
                <span className="text-muted-foreground">chunks</span>
              </div>
              {isIndexing && (
                <div className="flex items-center gap-1.5 text-primary">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span className="text-xs">Indexing...</span>
                </div>
              )}
            </div>
            {staleIgnored && staleIgnored.count > 0 && (
              <div className="flex items-center justify-between mt-3 pt-3 border-t text-sm">
                <div className="flex items-center gap-1.5 text-warning">
                  <ShieldAlert className="h-4 w-4 shrink-0" />
                  <span>
                    <span className="font-medium">{staleIgnored.count}</span>
                    <span className="text-muted-foreground ml-1">
                      indexed {staleIgnored.count === 1 ? "file matches" : "files match"} an ignore pattern and still
                      have chunks in the vector store
                    </span>
                  </span>
                </div>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handlePurgeStale}
                  disabled={purgingStale}
                  className="shrink-0 ml-4"
                >
                  {purgingStale ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                  )}
                  Purge {staleIgnored.count} {staleIgnored.count === 1 ? "file" : "files"}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FolderGit2 className="h-4 w-4" />
                Project Directories
              </CardTitle>
              <CardDescription>
                Index documentation from project repositories. Each immediate subdirectory of the path is treated as a
                project. The include patterns control which files within each project are indexed — use exclude to skip
                test directories, build artifacts, or other noise.
              </CardDescription>
            </div>
            {!showAddRoot && (
              <Button variant="outline" size="sm" onClick={() => setShowAddRoot(true)}>
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {showAddRoot && (
            <ProjectRootForm
              submitLabel="Add Project Root"
              onCancel={() => setShowAddRoot(false)}
              onSubmit={async (path, include, exclude, title) => {
                setShowAddRoot(false)
                const result = await onAddProjectRoot(path, include, exclude, title)
                if (result?.docker_restart_required) {
                  toast.warning(
                    `Project root added — restart required to mount "${path}" into the container: make docker-down && make docker-up`,
                  )
                } else if (result?.path_not_found) {
                  toast.warning(`Project root added but "${path}" does not exist — check the path`)
                } else {
                  toast.success(`Added project root "${title || path}" — scanning for projects`)
                }
              }}
            />
          )}

          {projectRoots.map((root) => (
            <div key={root.path} className="space-y-2">
              {editingRoot === root.path ? (
                <ProjectRootForm
                  initial={root}
                  submitLabel="Save"
                  onCancel={() => setEditingRoot(null)}
                  onSubmit={async (_path, include, exclude, title) => {
                    setEditingRoot(null)
                    await onUpdateProjectRoot(root.path, include, exclude, title)
                    toast.success(`Updated "${title || root.path}"`)
                  }}
                />
              ) : (
                <div className="rounded-md border p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <PathBadge path={root.path} />
                    <div className="flex-1 min-w-0">
                      {root.title && <p className="text-sm font-medium truncate">{root.title}</p>}
                      <span className="font-mono text-xs text-muted-foreground truncate block">{root.path}</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => setEditingRoot(root.path)}
                      aria-label={`Edit ${root.path}`}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => setPendingRemoveRoot(root.path)}
                      aria-label={`Remove ${root.path}`}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(root.include ?? []).map((p) => (
                      <Badge key={p} variant="secondary" className="font-mono text-xs">
                        {p}
                      </Badge>
                    ))}
                    {(root.exclude ?? []).map((p) => (
                      <Badge key={`ex-${p}`} variant="outline" className="font-mono text-xs line-through opacity-60">
                        {p}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}

          {projectRoots.length === 0 && !showAddRoot && (
            <p className="text-sm text-muted-foreground">No project directories configured.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Watch Directories</CardTitle>
          <CardDescription>
            Directories that MarkdownKB monitors for documents. Files in these directories are scanned, chunked, and
            embedded into the vector store for RAG search. Each source can be configured as writable (accepts
            mdkb-authored writes) and versioned (auto-commits those writes to a managed git repo).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {vstatus && vstatus.sources.length > 0 && (
            <div className="rounded-md bg-muted/30 px-3 py-2 flex items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <GitBranch className="h-3 w-3" />
                {vstatus.total_commits} commits across {vstatus.sources.filter((s) => s.initialised).length} repos
              </span>
              <span className="flex items-center gap-1">
                <HardDrive className="h-3 w-3" />
                {formatSize(vstatus.total_size_bytes)} on disk
              </span>
              {!coreVersioningEnabled && (
                <span className="text-yellow-600 dark:text-yellow-400">
                  Versioning is globally disabled — toggle on in Plugins settings
                </span>
              )}
            </div>
          )}

          {sourceConfigs.map((cfg) => {
            // Prefer richer status from /api/versioning/status; fall back
            // to local-only info when that endpoint hasn't responded yet.
            const vs = vstatus?.sources.find((s) => s.path === cfg.path)
            const status = vs ?? {
              path: cfg.path,
              writable: cfg.writable,
              versioned: cfg.versioned,
              path_accessible: true,
              initialised: false,
              commit_count: 0,
              last_commit_date: null,
              size_bytes: 0,
            }
            return (
              <VersioningSourceRow
                key={cfg.path}
                status={status}
                globalVersioningEnabled={coreVersioningEnabled}
                onRemove={() => setPendingRemove(cfg.path)}
                onUpdated={() => {
                  reloadVersioningStatus()
                  onReloadSettings()
                }}
              />
            )
          })}

          {/* Project-root-expanded sources (read-only, not user-added explicitly) */}
          {sources
            .filter((s) => !sourceConfigs.some((c) => c.path === s))
            .map((s) => (
              <div key={s} className="rounded-md border border-dashed p-3 flex items-center gap-2">
                <PathBadge path={s} />
                <span className="font-mono text-sm flex-1 truncate">{s}</span>
                <Badge variant="outline" className="text-[10px]">
                  from project root
                </Badge>
              </div>
            ))}

          {sourceConfigs.length === 0 && sources.length === 0 && (
            <p className="text-sm text-muted-foreground">No watch directories configured.</p>
          )}
          <AddDirectoryForm
            onSubmit={async (path) => {
              await onAdd(path)
              toast.success(`Added "${path}" — indexing started in background`)
            }}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Exclude Patterns</CardTitle>
          <CardDescription>
            Glob patterns for files and directories to skip during indexing. Matching paths are ignored by both the
            scanner and file watcher.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {ignorePatterns.map((p) => (
            <div key={p} className="flex items-center gap-2">
              <span className="font-mono text-sm flex-1 truncate">{p}</span>
              <Button variant="ghost" size="icon" onClick={() => onRemoveIgnore(p)} aria-label={`Remove pattern ${p}`}>
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          ))}
          {ignorePatterns.length === 0 && (
            <p className="text-sm text-muted-foreground">No exclude patterns configured.</p>
          )}
          <div className="flex gap-2 pt-2">
            <Input
              value={newPattern}
              onChange={(e) => setNewPattern(e.target.value)}
              placeholder="**/node_modules/**"
              className="flex-1"
              onKeyDown={(e) => e.key === "Enter" && handleAddPattern()}
            />
            <Button onClick={handleAddPattern} disabled={!newPattern.trim()}>
              Add
            </Button>
          </div>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={!!pendingRemove}
        onOpenChange={(open) => {
          if (!open) setPendingRemove(null)
        }}
        title="Remove Watch Directory?"
        description={`Remove "${pendingRemove}" from watch list. You can also unindex all files that were indexed from this directory.`}
        confirmLabel="Remove & Unindex"
        cancelLabel="Remove Only"
        variant="destructive"
        onConfirm={async () => {
          if (pendingRemove) {
            const path = pendingRemove
            setPendingRemove(null)
            await onRemove(path, true)
            toast.success(`Removed "${path}" and unindexed its files`)
          }
        }}
        onCancel={async () => {
          if (pendingRemove) {
            const path = pendingRemove
            setPendingRemove(null)
            await onRemove(path, false)
            toast.success(`Removed "${path}" from watch list`)
          }
        }}
      />

      <ConfirmDialog
        open={!!pendingRemoveRoot}
        onOpenChange={(open) => {
          if (!open) setPendingRemoveRoot(null)
        }}
        title="Remove Project Directory?"
        description={`Remove "${pendingRemoveRoot}" from project roots. You can also unindex all files that were discovered from this root.`}
        confirmLabel="Remove & Unindex"
        cancelLabel="Remove Only"
        variant="destructive"
        onConfirm={async () => {
          if (pendingRemoveRoot) {
            const path = pendingRemoveRoot
            setPendingRemoveRoot(null)
            await onRemoveProjectRoot(path, true)
            toast.success(`Removed project root "${path}" and unindexed its files`)
          }
        }}
        onCancel={async () => {
          if (pendingRemoveRoot) {
            const path = pendingRemoveRoot
            setPendingRemoveRoot(null)
            await onRemoveProjectRoot(path, false)
            toast.success(`Removed project root "${path}"`)
          }
        }}
      />
    </div>
  )
}
