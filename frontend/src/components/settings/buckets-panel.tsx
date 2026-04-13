import { useCallback, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Database, Plus, Trash2, Clock, Infinity as InfinityIcon } from "lucide-react"
import { useBuckets, type Bucket, type CreateBucketParams } from "@/hooks/use-buckets"


function formatExpiry(expiresAt: string | null): string {
  if (!expiresAt) return "Never"
  const d = new Date(expiresAt + "Z")
  return d.toLocaleString()
}

export function BucketsPanel() {
  const { buckets, createBucket, deleteBucket, updateExpiration } = useBuckets()
  const [name, setName] = useState("")
  const [sourcePath, setSourcePath] = useState("")
  const [sourceGlob, setSourceGlob] = useState("**/*.md")
  const [expiresInSecs, setExpiresInSecs] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Bucket | null>(null)

  const handleCreate = useCallback(async () => {
    if (!name.trim() || !sourcePath.trim()) return
    setCreating(true)
    const params: CreateBucketParams = {
      name: name.trim(),
      sources: [{ path: sourcePath.trim(), glob: sourceGlob.trim() || "**/*.md" }],
    }
    if (expiresInSecs && expiresInSecs > 0) {
      params.expires_in = expiresInSecs
    }
    const result = await createBucket(params)
    if (result) {
      setName("")
      setSourcePath("")
      setSourceGlob("**/*.md")
      setExpiresInSecs(null)
    }
    setCreating(false)
  }, [name, sourcePath, sourceGlob, expiresInSecs, createBucket])

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
              <Label htmlFor="bucket-expires" className="text-xs">Expires in</Label>
              <Select
                value={expiresInSecs === null ? "permanent" : expiresInSecs === 3600 ? "1h" : expiresInSecs === 86400 ? "24h" : expiresInSecs === 604800 ? "7d" : ""}
                onValueChange={(v) => {
                  if (v === "permanent") setExpiresInSecs(null)
                  else if (v === "1h") setExpiresInSecs(3600)
                  else if (v === "24h") setExpiresInSecs(86400)
                  else if (v === "7d") setExpiresInSecs(604800)
                }}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue placeholder="Permanent" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="permanent">
                    <span className="flex items-center gap-1"><InfinityIcon className="h-3.5 w-3.5" /> Permanent</span>
                  </SelectItem>
                  <SelectItem value="1h">
                    <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> 1 hour</span>
                  </SelectItem>
                  <SelectItem value="24h">
                    <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> 24 hours</span>
                  </SelectItem>
                  <SelectItem value="7d">
                    <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> 7 days</span>
                  </SelectItem>
                </SelectContent>
              </Select>
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
                  className="p-2 rounded border text-xs space-y-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <Database className="h-3 w-3 text-muted-foreground shrink-0" />
                        <span className="font-medium truncate">{b.name}</span>
                      </div>
                      <div className="text-muted-foreground mt-0.5 space-x-2">
                        <span>{b.file_count} files</span>
                        <span>{b.chunk_count} chunks</span>
                      </div>
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
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground shrink-0">Expiration:</span>
                    <Select
                      value="__pick__"
                      onValueChange={async (v) => {
                        if (v === "permanent") await updateExpiration(b.id, null)
                        else if (v === "1h") await updateExpiration(b.id, 3600)
                        else if (v === "24h") await updateExpiration(b.id, 86400)
                        else if (v === "7d") await updateExpiration(b.id, 604800)
                      }}
                    >
                      <SelectTrigger className="h-6 text-[11px] w-36">
                        <SelectValue placeholder={b.expires_at ? formatExpiry(b.expires_at) : "Permanent"} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__pick__" disabled className="text-muted-foreground">
                          {b.expires_at ? `Current: ${formatExpiry(b.expires_at)}` : "Currently permanent"}
                        </SelectItem>
                        <SelectItem value="permanent">
                          <span className="flex items-center gap-1"><InfinityIcon className="h-2.5 w-2.5" /> Permanent</span>
                        </SelectItem>
                        <SelectItem value="1h">
                          <span className="flex items-center gap-1"><Clock className="h-2.5 w-2.5" /> 1 hour</span>
                        </SelectItem>
                        <SelectItem value="24h">
                          <span className="flex items-center gap-1"><Clock className="h-2.5 w-2.5" /> 24 hours</span>
                        </SelectItem>
                        <SelectItem value="7d">
                          <span className="flex items-center gap-1"><Clock className="h-2.5 w-2.5" /> 7 days</span>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
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
