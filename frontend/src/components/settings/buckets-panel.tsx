import { useCallback, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { Database, Plus, Trash2, Clock } from "lucide-react"
import { useBuckets, type Bucket, type CreateBucketParams } from "@/hooks/use-buckets"
import { toast } from "sonner"

function formatExpiry(expiresAt: string | null): string {
  if (!expiresAt) return "Never"
  const d = new Date(expiresAt + "Z")
  return d.toLocaleString()
}

export function BucketsPanel() {
  const { buckets, createBucket, deleteBucket, refresh } = useBuckets()
  const [name, setName] = useState("")
  const [sourcePath, setSourcePath] = useState("")
  const [sourceGlob, setSourceGlob] = useState("**/*.md")
  const [expiresIn, setExpiresIn] = useState<string>("")
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Bucket | null>(null)

  const handleCreate = useCallback(async () => {
    if (!name.trim() || !sourcePath.trim()) return
    setCreating(true)
    const params: CreateBucketParams = {
      name: name.trim(),
      sources: [{ path: sourcePath.trim(), glob: sourceGlob.trim() || "**/*.md" }],
    }
    if (expiresIn && parseInt(expiresIn) > 0) {
      params.expires_in = parseInt(expiresIn)
    }
    const result = await createBucket(params)
    if (result) {
      toast.success(`Bucket "${result.name}" created (${result.file_count} files, ${result.chunk_count} chunks)`)
      setName("")
      setSourcePath("")
      setExpiresIn("")
    }
    setCreating(false)
  }, [name, sourcePath, sourceGlob, expiresIn, createBucket])

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return
    await deleteBucket(deleteTarget.id)
    setDeleteTarget(null)
  }, [deleteTarget, deleteBucket])

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium mb-3">Create Bucket</h3>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="bucket-name" className="text-xs">Name</Label>
            <Input
              id="bucket-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-docs"
              className="h-8 text-sm"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="bucket-path" className="text-xs">Source path</Label>
            <Input
              id="bucket-path"
              value={sourcePath}
              onChange={(e) => setSourcePath(e.target.value)}
              placeholder="/path/to/docs"
              className="h-8 text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="bucket-glob" className="text-xs">Glob pattern</Label>
              <Input
                id="bucket-glob"
                value={sourceGlob}
                onChange={(e) => setSourceGlob(e.target.value)}
                placeholder="**/*.md"
                className="h-8 text-sm"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="bucket-expires" className="text-xs">Expires in (seconds)</Label>
              <Input
                id="bucket-expires"
                type="number"
                value={expiresIn}
                onChange={(e) => setExpiresIn(e.target.value)}
                placeholder="Optional"
                className="h-8 text-sm"
                min={60}
              />
            </div>
          </div>
          <Button
            onClick={handleCreate}
            disabled={creating || !name.trim() || !sourcePath.trim()}
            size="sm"
            className="w-full"
          >
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            {creating ? "Creating..." : "Create Bucket"}
          </Button>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium mb-3">
          Active Buckets
          {buckets.length > 0 && (
            <Badge variant="secondary" className="ml-2 text-[10px]">
              {buckets.length}
            </Badge>
          )}
        </h3>

        {buckets.length === 0 ? (
          <p className="text-xs text-muted-foreground">No buckets created yet.</p>
        ) : (
          <ScrollArea className="max-h-64">
            <div className="space-y-2">
              {buckets.map((b) => (
                <div
                  key={b.id}
                  className="flex items-start justify-between gap-2 p-2 rounded border text-xs"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <Database className="h-3 w-3 text-muted-foreground shrink-0" />
                      <span className="font-medium truncate">{b.name}</span>
                    </div>
                    <div className="text-muted-foreground mt-0.5 space-x-2">
                      <span>{b.file_count} files</span>
                      <span>{b.chunk_count} chunks</span>
                    </div>
                    {b.expires_at && (
                      <div className="text-muted-foreground mt-0.5 flex items-center gap-1">
                        <Clock className="h-2.5 w-2.5" />
                        <span>Expires: {formatExpiry(b.expires_at)}</span>
                      </div>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                    onClick={() => setDeleteTarget(b)}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
        title="Delete bucket?"
        description={`This will permanently delete bucket "${deleteTarget?.name}" and all its vector data.`}
        confirmLabel="Delete"
        onConfirm={handleDelete}
      />
    </div>
  )
}
