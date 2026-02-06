import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Trash2 } from "lucide-react"

export function SourcesPanel({
  sources,
  ignorePatterns,
  onAdd,
  onRemove,
  onAddIgnore,
  onRemoveIgnore,
}: {
  sources: string[]
  ignorePatterns: string[]
  onAdd: (path: string) => Promise<void>
  onRemove: (path: string) => Promise<void>
  onAddIgnore: (pattern: string) => Promise<void>
  onRemoveIgnore: (pattern: string) => Promise<void>
}) {
  const [newSource, setNewSource] = useState("")
  const [newPattern, setNewPattern] = useState("")

  async function handleAdd() {
    if (!newSource.trim()) return
    await onAdd(newSource.trim())
    setNewSource("")
  }

  async function handleAddPattern() {
    if (!newPattern.trim()) return
    await onAddIgnore(newPattern.trim())
    setNewPattern("")
  }

  return (
    <div className="space-y-4">
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
                onClick={() => onRemove(s)}
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
    </div>
  )
}
