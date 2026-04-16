import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Trash2 } from "lucide-react"
import { useBuckets, type Bucket } from "@/hooks/use-buckets"
import { useTableSort } from "@/hooks/use-table-sort"
import { relativeTime } from "@/lib/utils"

type BucketStatus = "active" | "expiring" | "expired"

function bucketStatus(b: Bucket): BucketStatus {
  if (b.expired) return "expired"
  if (b.expires_at) {
    const expiresMs = new Date(b.expires_at + "Z").getTime()
    const hoursRemaining = (expiresMs - Date.now()) / 1000 / 3600
    if (hoursRemaining < 24) return "expiring"
  }
  return "active"
}

function StatusBadge({ status }: { status: BucketStatus }) {
  if (status === "expired") {
    return (
      <Badge variant="outline" className="text-[10px] text-destructive border-destructive/40">
        Expired
      </Badge>
    )
  }
  if (status === "expiring") {
    return (
      <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-500/50">
        Expiring soon
      </Badge>
    )
  }
  return (
    <Badge variant="secondary" className="text-[10px]">
      Active
    </Badge>
  )
}

function getValue(b: Bucket, key: string): string | number | null {
  if (key === "name") return b.name
  if (key === "file_count") return b.file_count
  if (key === "chunk_count") return b.chunk_count
  if (key === "created_at") return b.created_at
  if (key === "expires_at") return b.expires_at ?? ""
  if (key === "status") return bucketStatus(b)
  return null
}

function SortHeader({
  label,
  sortKey,
  currentKey,
  currentDir,
  onSort,
}: {
  label: string
  sortKey: string
  currentKey: string | null
  currentDir: "asc" | "desc"
  onSort: (key: string) => void
}) {
  const active = currentKey === sortKey
  return (
    <button
      type="button"
      className="flex items-center gap-1 text-left font-medium hover:text-foreground transition-colors"
      onClick={() => onSort(sortKey)}
    >
      {label}
      {active && (
        <span className="text-[10px] text-muted-foreground">
          {currentDir === "asc" ? "↑" : "↓"}
        </span>
      )}
    </button>
  )
}

export function BucketsPanel() {
  const { buckets, deleteBucket } = useBuckets()
  const [deleteTarget, setDeleteTarget] = useState<Bucket | null>(null)

  const { sorted, sortKey, sortDir, onSort } = useTableSort(
    buckets,
    getValue,
    "created_at",
  )

  async function handleDelete() {
    if (!deleteTarget) return
    await deleteBucket(deleteTarget.id)
    setDeleteTarget(null)
  }

  const headerProps = { currentKey: sortKey, currentDir: sortDir, onSort }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Bucket History</h3>
        {buckets.length > 0 && (
          <span className="text-xs text-muted-foreground">{buckets.length} bucket{buckets.length !== 1 ? "s" : ""}</span>
        )}
      </div>

      {buckets.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No buckets. Create one on the Buckets tab.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <SortHeader label="Name" sortKey="name" {...headerProps} />
              </TableHead>
              <TableHead>
                <SortHeader label="Files" sortKey="file_count" {...headerProps} />
              </TableHead>
              <TableHead>
                <SortHeader label="Created" sortKey="created_at" {...headerProps} />
              </TableHead>
              <TableHead>
                <SortHeader label="Expires" sortKey="expires_at" {...headerProps} />
              </TableHead>
              <TableHead>
                <SortHeader label="Status" sortKey="status" {...headerProps} />
              </TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((b) => {
              const status = bucketStatus(b)
              return (
                <TableRow key={b.id} className={b.expired ? "opacity-60" : undefined}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span
                        className="h-2 w-2 rounded-full shrink-0"
                        style={{ backgroundColor: b.color ?? "var(--bucket-default)" }}
                      />
                      <span className="font-medium text-xs">{b.name}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground tabular-nums">
                    {b.file_count}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {relativeTime(b.created_at)}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {b.expires_at
                      ? new Date(b.expires_at + "Z").toLocaleDateString()
                      : "—"}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={status} />
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 text-muted-foreground hover:text-destructive"
                      title="Delete bucket"
                      onClick={() => setDeleteTarget(b)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}
        title="Delete bucket?"
        description={`This will permanently delete bucket "${deleteTarget?.name}" and all its vector data.`}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={handleDelete}
      />
    </div>
  )
}
