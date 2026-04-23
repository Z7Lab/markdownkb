import { useEffect } from "react"
import { SidebarSection } from "@/components/ui/sidebar-section"
import { Checkbox } from "@/components/ui/checkbox"
import { Database } from "lucide-react"
import type { Bucket } from "@/hooks/use-buckets"

export function BucketSelector({
  buckets,
  selectedBucketIds,
  onBucketChange,
}: {
  buckets: Bucket[]
  selectedBucketIds: Set<string>
  onBucketChange: (ids: Set<string>) => void
}) {
  const activeBuckets = buckets.filter((b) => !b.expired)

  // Clear stale bucket selections (expired/deleted buckets)
  useEffect(() => {
    if (selectedBucketIds.size === 0) return
    const validIds = new Set(activeBuckets.map((b) => b.id))
    const stale = Array.from(selectedBucketIds).filter((id) => !validIds.has(id))
    if (stale.length > 0) {
      const next = new Set(selectedBucketIds)
      stale.forEach((id) => next.delete(id))
      onBucketChange(next)
    }
  }, [selectedBucketIds, buckets, onBucketChange])

  if (activeBuckets.length === 0) return null

  function toggle(id: string, checked: boolean) {
    const next = new Set(selectedBucketIds)
    if (checked) next.add(id)
    else next.delete(id)
    onBucketChange(next)
  }

  const selectedNames = activeBuckets
    .filter((b) => selectedBucketIds.has(b.id))
    .map((b) => b.name)
    .join(", ")

  return (
    <SidebarSection
      icon={Database}
      label="Buckets"
      count={selectedBucketIds.size}
      summary={selectedNames || undefined}
    >
      <div className="space-y-0.5 pl-2">
        {activeBuckets.map((b) => (
          <label
            key={b.id}
            className="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent cursor-pointer text-xs"
          >
            <Checkbox
              checked={selectedBucketIds.has(b.id)}
              onCheckedChange={(checked) => toggle(b.id, !!checked)}
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
