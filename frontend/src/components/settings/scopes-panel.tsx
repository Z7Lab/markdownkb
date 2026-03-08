import { useState } from "react"
import { useScopes } from "@/hooks/use-scopes"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Plus, Pencil, Trash2, X, Check } from "lucide-react"

export function ScopesPanel({ folders }: { folders: string[] }) {
  const { scopes, createScope, updateScope, deleteScope } = useScopes()
  const [isCreating, setIsCreating] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [name, setName] = useState("")
  const [selectedFolders, setSelectedFolders] = useState<Set<string>>(new Set())

  function startCreate() {
    setIsCreating(true)
    setEditingId(null)
    setName("")
    setSelectedFolders(new Set())
  }

  function startEdit(scope: { id: string; name: string; folders: string[] }) {
    setEditingId(scope.id)
    setIsCreating(false)
    setName(scope.name)
    setSelectedFolders(new Set(scope.folders))
  }

  function cancel() {
    setIsCreating(false)
    setEditingId(null)
    setName("")
    setSelectedFolders(new Set())
  }

  async function save() {
    if (!name.trim() || selectedFolders.size === 0) return
    const folderList = Array.from(selectedFolders)
    if (editingId) {
      await updateScope(editingId, name.trim(), folderList)
    } else {
      await createScope(name.trim(), folderList)
    }
    cancel()
  }

  function toggleFolder(folder: string) {
    setSelectedFolders((prev) => {
      const next = new Set(prev)
      if (next.has(folder)) {
        next.delete(folder)
      } else {
        next.add(folder)
      }
      return next
    })
  }

  const isEditing = isCreating || editingId !== null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Scopes</h2>
          <p className="text-sm text-muted-foreground">
            Named subsets of your sources. Use scopes to focus Chat, Search, and Planner on specific document collections.
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
              autoFocus
            />
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground font-medium">
                Select folders to include:
              </p>
              {folders.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No source folders configured. Add sources in the Sources panel first.
                </p>
              ) : (
                <div className="space-y-1 max-h-48 overflow-y-auto">
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
            <div className="flex gap-2 pt-1">
              <Button
                size="sm"
                onClick={save}
                disabled={!name.trim() || selectedFolders.size === 0}
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
              </div>
            </div>
            <div className="flex gap-1 shrink-0">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => startEdit(scope)}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive"
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
