import { Button } from "@/components/ui/button"
import { EmptyHero } from "@/components/ui/empty-hero"
import { Database, Plus } from "lucide-react"

export interface BucketsEmptyStateProps {
  onNewBucket: () => void
}

export function BucketsEmptyState({ onNewBucket }: BucketsEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4">
      <EmptyHero icon={Database} label="Buckets" />
      <p className="text-sm text-muted-foreground text-center max-w-sm">
        Buckets are temporary document collections for focused analysis.
        Create one to load external docs, vendor APIs, or research material
        without mixing them into your permanent knowledge base.
      </p>
      <Button size="sm" className="gap-1.5" onClick={onNewBucket}>
        <Plus className="h-4 w-4" />
        New Bucket
      </Button>
    </div>
  )
}
