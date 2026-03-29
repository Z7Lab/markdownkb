import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { ChevronDown, ChevronRight, Database } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { Bucket } from "@/hooks/use-buckets"

export function BucketSelector({
  buckets,
  selectedBucketId,
  onBucketChange,
}: {
  buckets: Bucket[]
  selectedBucketId: string | null
  onBucketChange: (id: string | null) => void
}) {
  const [open, setOpen] = useState(false)

  if (buckets.length === 0) return null

  return (
    <div className="space-y-1 px-1">
      <button
        className="flex items-center gap-2 w-full text-left"
        onClick={() => setOpen(!open)}
      >
        {open ? (
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 text-muted-foreground" />
        )}
        <Database className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        <span className="text-xs font-medium text-muted-foreground">Buckets</span>
        {selectedBucketId && (
          <Badge variant="secondary" className="text-[10px] h-4 px-1 ml-auto">
            1
          </Badge>
        )}
      </button>

      {open && (
        <div className="pl-5">
          <Select
            value={selectedBucketId ?? "__none__"}
            onValueChange={(v) => onBucketChange(v === "__none__" ? null : v)}
          >
            <SelectTrigger className="h-7 text-xs">
              <SelectValue placeholder="All sources" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">All sources</SelectItem>
              {buckets.map((b) => (
                <SelectItem key={b.id} value={b.id}>
                  {b.name}
                  <span className="text-muted-foreground ml-1">
                    ({b.file_count} files)
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
    </div>
  )
}
