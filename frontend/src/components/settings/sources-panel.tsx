import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { useIndexEvents } from "@/hooks/use-index-events"
import { api } from "@/lib/api"
import type { ProjectRoot } from "@/lib/types"
import { CheckCircle2, AlertCircle, Loader2, Trash2, FileText, Pencil, Plus, X, FolderGit2 } from "lucide-react"
import { toast } from "sonner"

function ProjectRootForm({
  initial,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  initial?: ProjectRoot
  onSubmit: (path: string, include: string[], exclude: string[]) => void
  onCancel: () => void
  submitLabel: string
}) {
  const [path, setPath] = useState(initial?.path ?? "")
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
        <Input
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="/home/user/projects"
          onKeyDown={(e) => e.key === "Enter" && canSubmit && onSubmit(path.trim(), include, exclude)}
        />
      )}

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
          {exclude.length === 0 && (
            <span className="text-xs text-muted-foreground italic">None</span>
          )}
        </div>
        <div className="flex gap-2">
          <Input
            value={excludeInput}
            onChange={(e) => setExcludeInput(e.target.value)}
            placeholder="CHANGELOG.md"
            className="flex-1 h-8 text-xs"
            onKeyDown={(e) => e.key === "Enter" && addExclude()}
          />
          <Button variant="outline" size="sm" onClick={addExclude} disabled={!excludeInput.trim()}>
            <Plus className="h-3 w-3" />
          </Button>
        </div>
      </div>

      <div className="flex gap-2 justify-end pt-1">
        <Button variant="ghost" size="sm" onClick={onCancel}>Cancel</Button>
        <Button
          size="sm"
          onClick={() => onSubmit(path.trim(), include, exclude)}
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
  ignorePatterns,
  projectRoots,
  onAdd,
  onRemove,
  onAddIgnore,
  onRemoveIgnore,
  onAddProjectRoot,
  onRemoveProjectRoot,
  onUpdateProjectRoot,
}: {
  sources: string[]
  ignorePatterns: string[]
  projectRoots: ProjectRoot[]
  onAdd: (path: string) => Promise<void>
  onRemove: (path: string, cleanup: boolean) => Promise<void>
  onAddIgnore: (pattern: string) => Promise<void>
  onRemoveIgnore: (pattern: string) => Promise<void>
  onAddProjectRoot: (path: string, include: string[], exclude: string[]) => Promise<void>
  onRemoveProjectRoot: (path: string, cleanup: boolean) => Promise<void>
  onUpdateProjectRoot: (path: string, include: string[], exclude: string[]) => Promise<void>
}) {
  const [newSource, setNewSource] = useState("")
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
  const { isIndexing, lastIndexedAt } = useIndexEvents()

  useEffect(() => {
    api.get<{
      files_tracked: number
      files_complete: number
      files_error: number
      chunks_indexed: number
    }>("/api/stats").then(setStats).catch(() => {})
  }, [lastIndexedAt])

  async function handleAdd() {
    if (!newSource.trim()) return
    const path = newSource.trim()
    setNewSource("")
    await onAdd(path)
    toast.success(`Added "${path}" — indexing started in background`)
  }

  async function handleAddPattern() {
    if (!newPattern.trim()) return
    await onAddIgnore(newPattern.trim())
    setNewPattern("")
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
                Automatically discover and index documentation from project
                repositories. Point to a directory containing cloned repos and
                define which file patterns to index.
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
              onSubmit={async (path, include, exclude) => {
                setShowAddRoot(false)
                await onAddProjectRoot(path, include, exclude)
                toast.success(`Added project root "${path}" — scanning for projects`)
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
                  onSubmit={async (_path, include, exclude) => {
                    setEditingRoot(null)
                    await onUpdateProjectRoot(root.path, include, exclude)
                    toast.success(`Updated patterns for "${root.path}"`)
                  }}
                />
              ) : (
                <div className="rounded-md border p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-mono text-sm flex-1 truncate">{root.path}</span>
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
                      <Badge key={p} variant="secondary" className="font-mono text-xs">{p}</Badge>
                    ))}
                    {(root.exclude ?? []).map((p) => (
                      <Badge key={`ex-${p}`} variant="outline" className="font-mono text-xs line-through opacity-60">{p}</Badge>
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
            Directories that mdkb monitors for documents. Files in these
            directories are scanned, chunked, and embedded into the vector
            store for RAG search. Changes are detected automatically via
            file watcher.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {sources.map((s) => (
            <div key={s} className="flex items-center gap-2">
              <span className="font-mono text-sm flex-1 truncate">{s}</span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setPendingRemove(s)}
                aria-label={`Remove ${s}`}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          ))}
          {sources.length === 0 && (
            <p className="text-sm text-muted-foreground">No watch directories configured.</p>
          )}
          <div className="flex gap-2 pt-2">
            <Input
              value={newSource}
              onChange={(e) => setNewSource(e.target.value)}
              placeholder="/path/to/documents"
              className="flex-1"
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            />
            <Button onClick={handleAdd} disabled={!newSource.trim()}>
              Add
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Exclude Patterns</CardTitle>
          <CardDescription>
            Glob patterns for files and directories to skip during
            indexing. Matching paths are ignored by both the scanner
            and file watcher.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {ignorePatterns.map((p) => (
            <div key={p} className="flex items-center gap-2">
              <span className="font-mono text-sm flex-1 truncate">{p}</span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => onRemoveIgnore(p)}
                aria-label={`Remove pattern ${p}`}
              >
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
        onOpenChange={(open) => { if (!open) setPendingRemove(null) }}
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
        onOpenChange={(open) => { if (!open) setPendingRemoveRoot(null) }}
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
