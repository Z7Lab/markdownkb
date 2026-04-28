import { useState } from "react"
import { useScopes } from "@/hooks/use-scopes"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Plus, Pencil, Trash2, X, Check, Tag, Ban } from "lucide-react"
import type { ProjectRoot } from "@/lib/types"

function getExpandedSources(root: ProjectRoot, allSources: string[]): string[] {
  return allSources.filter((s) => {
    if (!s.startsWith(root.path + "/")) return false
    return !s.slice(root.path.length + 1).includes("/")
  })
}

export function ScopesPanel({
  folders,
  allSources,
  projectRoots,
  availableTags,
}: {
  folders: string[]
  allSources: string[]
  projectRoots: ProjectRoot[]
  availableTags: string[]
}) {
  const { scopes, createScope, updateScope, deleteScope } = useScopes()
  const [isCreating, setIsCreating] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [name, setName] = useState("")
  const [selectedFolders, setSelectedFolders] = useState<Set<string>>(new Set())
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set())
  const [newTag, setNewTag] = useState("")
  const [excludePatterns, setExcludePatterns] = useState<string[]>([])
  const [newExclude, setNewExclude] = useState("")

  function startCreate() {
    setIsCreating(true)
    setEditingId(null)
    setName("")
    setSelectedFolders(new Set())
    setSelectedTags(new Set())
    setExcludePatterns([])
  }

  function startEdit(scope: { id: string; name: string; folders: string[]; tags: string[]; exclude_patterns: string[] }) {
    setEditingId(scope.id)
    setIsCreating(false)
    setName(scope.name)
    setSelectedFolders(new Set(scope.folders))
    setSelectedTags(new Set(scope.tags))
    setExcludePatterns(scope.exclude_patterns || [])
  }

  function cancel() {
    setIsCreating(false)
    setEditingId(null)
    setName("")
    setSelectedFolders(new Set())
    setSelectedTags(new Set())
    setNewTag("")
    setExcludePatterns([])
    setNewExclude("")
  }

  async function save() {
    if (!name.trim() || (selectedFolders.size === 0 && selectedTags.size === 0)) return
    const folderList = Array.from(selectedFolders)
    const tagList = Array.from(selectedTags)
    if (editingId) {
      await updateScope(editingId, name.trim(), folderList, tagList, excludePatterns)
    } else {
      await createScope(name.trim(), folderList, tagList, excludePatterns)
    }
    cancel()
  }

  function addExclude() {
    const pat = newExclude.trim()
    if (pat && !excludePatterns.includes(pat)) {
      setExcludePatterns([...excludePatterns, pat])
      setNewExclude("")
    }
  }

  function removeExclude(pat: string) {
    setExcludePatterns(excludePatterns.filter((p) => p !== pat))
  }

  function toggleFolder(folder: string) {
    setSelectedFolders((prev) => {
      const next = new Set(prev)
      if (next.has(folder)) next.delete(folder)
      else next.add(folder)
      return next
    })
  }

  function toggleProjectRoot(root: ProjectRoot) {
    const expanded = getExpandedSources(root, allSources)
    const allSelected = expanded.length > 0 && expanded.every((s) => selectedFolders.has(s))
    setSelectedFolders((prev) => {
      const next = new Set(prev)
      if (allSelected) expanded.forEach((s) => next.delete(s))
      else expanded.forEach((s) => next.add(s))
      return next
    })
  }

  function projectRootChecked(root: ProjectRoot): boolean {
    const expanded = getExpandedSources(root, allSources)
    return expanded.length > 0 && expanded.every((s) => selectedFolders.has(s))
  }

  function projectRootIndeterminate(root: ProjectRoot): boolean {
    const expanded = getExpandedSources(root, allSources)
    const selected = expanded.filter((s) => selectedFolders.has(s))
    return selected.length > 0 && selected.length < expanded.length
  }

  function toggleTag(tag: string) {
    setSelectedTags((prev) => {
      const next = new Set(prev)
      if (next.has(tag)) next.delete(tag)
      else next.add(tag)
      return next
    })
  }

  function addCustomTag() {
    const tag = newTag.trim()
    if (tag) {
      setSelectedTags((prev) => new Set(prev).add(tag))
      setNewTag("")
    }
  }

  const isEditing = isCreating || editingId !== null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Scopes</h2>
          <p className="text-sm text-muted-foreground">
            Named subsets of your sources. Filter by folders, tags, or both.
          </p>
        </div>
        {!isEditing && (
          <Button onClick={startCreate} size="sm" className="gap-1.5">
            <Plus className="h-4 w-4" />
            New Scope
          </Button>
        )}
      </div>

      {isEditing && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">
              {editingId ? "Edit Scope" : "New Scope"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Scope name (e.g. Infrastructure Docs)"
              aria-label="Scope name"
              autoFocus
            />
            {projectRoots.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs text-muted-foreground font-medium">Project Directories (optional):</p>
                <div className="space-y-1 max-h-36 overflow-y-auto">
                  {projectRoots.map((root) => (
                    <label
                      key={root.path}
                      className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-accent cursor-pointer text-sm"
                    >
                      <Checkbox
                        checked={projectRootChecked(root)}
                        data-state={projectRootIndeterminate(root) ? "indeterminate" : undefined}
                        onCheckedChange={() => toggleProjectRoot(root)}
                      />
                      <span className="truncate">{root.title || root.path.split("/").pop() || root.path}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground font-medium">
                Watch Directories (optional):
              </p>
              {folders.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No watch directories configured.
                </p>
              ) : (
                <div className="space-y-1 max-h-36 overflow-y-auto">
                  {folders.map((f) => (
                    <label
                      key={f}
                      className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-accent cursor-pointer text-sm"
                    >
                      <Checkbox
                        checked={selectedFolders.has(f)}
                        onCheckedChange={() => toggleFolder(f)}
                      />
                      <span className="truncate">{f}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground font-medium">
                Tags (optional):
              </p>
              {availableTags.length > 0 && (
                <div className="space-y-1 max-h-36 overflow-y-auto">
                  {availableTags.map((t) => (
                    <label
                      key={t}
                      className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-accent cursor-pointer text-sm"
                    >
                      <Checkbox
                        checked={selectedTags.has(t)}
                        onCheckedChange={() => toggleTag(t)}
                      />
                      <span className="truncate">{t}</span>
                    </label>
                  ))}
                </div>
              )}
              <div className="flex gap-1.5">
                <Input
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  placeholder="Add custom tag..."
                  className="h-8 text-xs"
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCustomTag() } }}
                />
                <Button size="sm" variant="outline" className="h-8 px-2" onClick={addCustomTag} disabled={!newTag.trim()}>
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
              {selectedTags.size > 0 && (
                <div className="flex flex-wrap gap-1">
                  {Array.from(selectedTags).map((t) => (
                    <Badge key={t} variant="outline" className="text-xs gap-1 cursor-pointer" onClick={() => toggleTag(t)}>
                      <Tag className="h-2.5 w-2.5" />
                      {t}
                      <X className="h-2.5 w-2.5" />
                    </Badge>
                  ))}
                </div>
              )}
            </div>
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground font-medium">
                Exclude patterns (optional):
              </p>
              <p className="text-xs text-muted-foreground">
                Glob patterns to exclude from this scope. Matched against the full file path and filename.
              </p>
              <div className="flex gap-1.5">
                <Input
                  value={newExclude}
                  onChange={(e) => setNewExclude(e.target.value)}
                  placeholder="e.g. agent-reviewed-* or **/archive/**"
                  className="h-8 text-xs"
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addExclude() } }}
                />
                <Button size="sm" variant="outline" className="h-8 px-2" onClick={addExclude} disabled={!newExclude.trim()}>
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
              {excludePatterns.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {excludePatterns.map((p) => (
                    <Badge key={p} variant="outline" className="text-xs gap-1 cursor-pointer text-destructive border-destructive/30" onClick={() => removeExclude(p)}>
                      <Ban className="h-2.5 w-2.5" />
                      {p}
                      <X className="h-2.5 w-2.5" />
                    </Badge>
                  ))}
                </div>
              )}
            </div>
            <div className="flex gap-2 pt-1">
              <Button
                size="sm"
                onClick={save}
                disabled={!name.trim() || (selectedFolders.size === 0 && selectedTags.size === 0)}
                className="gap-1"
              >
                <Check className="h-3.5 w-3.5" />
                {editingId ? "Update" : "Create"}
              </Button>
              <Button size="sm" variant="ghost" onClick={cancel} className="gap-1">
                <X className="h-3.5 w-3.5" />
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {scopes.length === 0 && !isEditing && (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            No scopes yet. Create one to focus your searches on specific source collections.
          </CardContent>
        </Card>
      )}

      {scopes.map((scope) => (
        <Card key={scope.id}>
          <CardContent className="py-3 flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <p className="font-medium text-sm">{scope.name}</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {scope.folders.map((f) => (
                  <Badge key={f} variant="secondary" className="text-xs font-normal">
                    {f.split("/").pop() || f}
                  </Badge>
                ))}
                {scope.tags.map((t) => (
                  <Badge key={t} variant="outline" className="text-xs font-normal gap-1">
                    <Tag className="h-2.5 w-2.5" />
                    {t}
                  </Badge>
                ))}
                {(scope.exclude_patterns || []).map((p) => (
                  <Badge key={p} variant="outline" className="text-xs font-normal gap-1 text-destructive border-destructive/30">
                    <Ban className="h-2.5 w-2.5" />
                    {p}
                  </Badge>
                ))}
              </div>
            </div>
            <div className="flex gap-1 shrink-0">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label="Edit scope"
                onClick={() => startEdit(scope)}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                aria-label="Delete scope"
                onClick={() => deleteScope(scope.id)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
