import { useEffect } from "react"
import { SidebarSection } from "@/components/ui/sidebar-section"
import { Checkbox } from "@/components/ui/checkbox"
import { Database } from "lucide-react"
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
  // Clear stale bucket selection (expired/deleted bucket)
  useEffect(() => {
    if (selectedBucketId && buckets.length > 0 && !buckets.some((b) => b.id === selectedBucketId)) {
      onBucketChange(null)
    }
  }, [selectedBucketId, buckets, onBucketChange])

  if (buckets.length === 0) return null

  const selectedName = selectedBucketId
    ? buckets.find((b) => b.id === selectedBucketId)?.name
    : undefined

  return (
    <SidebarSection
      icon={Database}
      label="Buckets"
      count={selectedBucketId ? 1 : 0}
      summary={selectedName}
    >
      <div className="space-y-0.5 pl-2">
        {buckets.map((b) => (
          <label
            key={b.id}
            className="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent cursor-pointer text-xs"
          >
            <Checkbox
              checked={selectedBucketId === b.id}
              onCheckedChange={(checked) => onBucketChange(checked ? b.id : null)}
            />
            <span className="truncate flex-1">{b.name}</span>
            <span className="text-[10px] text-muted-foreground shrink-0">
              {b.file_count} files
            </span>
          </label>
        ))}
      </div>
    </SidebarSection>
  )
}
