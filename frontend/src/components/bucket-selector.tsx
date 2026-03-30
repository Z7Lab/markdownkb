import { SidebarSection } from "@/components/ui/sidebar-section"
import { Database } from "lucide-react"
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
    </SidebarSection>
  )
}
