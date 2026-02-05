import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Trash2 } from "lucide-react"

export function SourcesPanel({
  sources,
  onAdd,
  onRemove,
}: {
  sources: string[]
  onAdd: (path: string) => Promise<void>
  onRemove: (path: string) => Promise<void>
}) {
  const [newSource, setNewSource] = useState("")

  async function handleAdd() {
    if (!newSource.trim()) return
    await onAdd(newSource.trim())
    setNewSource("")
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Source Directories</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {sources.map((s) => (
          <div key={s} className="flex items-center gap-2">
            <span className="font-mono text-sm flex-1 truncate">{s}</span>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onRemove(s)}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        ))}
        {sources.length === 0 && (
          <p className="text-sm text-muted-foreground">No sources configured.</p>
        )}
        <div className="flex gap-2 pt-2">
          <Input
            value={newSource}
            onChange={(e) => setNewSource(e.target.value)}
            placeholder="/path/to/markdown/files"
            className="flex-1"
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          />
          <Button onClick={handleAdd} disabled={!newSource.trim()}>
            Add
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
