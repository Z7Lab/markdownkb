import { AppSidebar } from "@/components/ui/app-sidebar"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Plus } from "lucide-react"
import { cn } from "@/lib/utils"
import type { Bucket } from "@/hooks/use-buckets"

export function BucketsSidebar({
  buckets,
  selectedId,
  onSelect,
  onNewBucket,
}: {
  buckets: Bucket[]
  selectedId: string | null
  onSelect: (id: string) => void
  onNewBucket: () => void
}) {
  return (
    <AppSidebar
      header={
        <Button
          variant="outline"
          className="w-full justify-start gap-2"
          onClick={onNewBucket}
        >
          <Plus className="h-4 w-4" />
          New Bucket
        </Button>
      }
    >
      <div className="p-2 space-y-0.5">
        {buckets.length === 0 && (
          <p className="text-xs text-muted-foreground px-2 py-4 text-center">
            No buckets yet
          </p>
        )}
        {buckets.map((bucket) => (
          <button
            key={bucket.id}
            type="button"
            onClick={() => onSelect(bucket.id)}
            className={cn(
              "w-full text-left flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors",
              "hover:bg-accent hover:text-accent-foreground",
              selectedId === bucket.id
                ? "bg-accent text-accent-foreground"
                : "text-foreground/80",
              bucket.expired && "opacity-60",
            )}
          >
            <span
              className="h-2.5 w-2.5 rounded-full shrink-0"
              style={{ backgroundColor: bucket.color ?? "#ff3333" }}
            />
            <span className="flex-1 min-w-0 truncate">{bucket.name}</span>
            {bucket.expired ? (
              <Badge
                variant="outline"
                className="text-[10px] text-destructive border-destructive/40 shrink-0 px-1 py-0"
              >
                expired
              </Badge>
            ) : (
              <span className="text-[10px] text-muted-foreground shrink-0 tabular-nums">
                {bucket.file_count}
              </span>
            )}
          </button>
        ))}
      </div>
    </AppSidebar>
  )
}

