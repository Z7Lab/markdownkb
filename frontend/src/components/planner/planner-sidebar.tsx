import { Button } from "@/components/ui/button"
import { AppSidebar } from "@/components/ui/app-sidebar"
import { SidebarItemList } from "@/components/ui/sidebar-item-list"
import { Bot, Lightbulb, Plus } from "lucide-react"
import type { SavedPlan, Scope } from "@/lib/types"
import type { Bucket } from "@/hooks/use-buckets"
import { FilterPicker } from "@/components/filter-picker"

function isAgentPlan(p: SavedPlan): boolean {
  return p.title?.startsWith("[agent]") ?? false
}

function displayLabel(p: SavedPlan): string {
  const label = p.query || p.title
  if (isAgentPlan(p)) return label.replace(/^\[agent\]\s*/, "")
  return label
}

export function PlannerSidebar({
  plans,
  activePlanId,
  scopes,
  selectedScopeIds,
  onScopeChange,
  availableTags,
  selectedTags,
  onTagChange,
  buckets,
  selectedBucketIds,
  onBucketChange,
  onNewPlan,
  onLoadPlan,
  onRenamePlan,
  onDeletePlan,
}: {
  plans: SavedPlan[]
  activePlanId: string | null
  scopes: Scope[]
  selectedScopeIds: Set<string>
  onScopeChange: (ids: Set<string>) => void
  availableTags: string[]
  selectedTags: Set<string>
  onTagChange: (tags: Set<string>) => void
  buckets: Bucket[]
  selectedBucketIds: Set<string>
  onBucketChange: (ids: Set<string>) => void
  onNewPlan: () => void
  onLoadPlan: (planId: string) => void
  onRenamePlan: (planId: string, title: string) => void
  onDeletePlan: (planId: string) => void
}) {
  return (
    <AppSidebar
      header={
        <div className="space-y-2">
          <Button
            onClick={onNewPlan}
            variant="outline"
            className="w-full justify-start gap-2"
          >
            <Plus className="h-4 w-4" />
            New Plan
          </Button>
          <FilterPicker
            scopes={scopes}
            selectedScopeIds={selectedScopeIds}
            onScopeChange={onScopeChange}
            availableTags={availableTags}
            selectedTags={selectedTags}
            onTagChange={onTagChange}
            buckets={buckets}
            selectedBucketIds={selectedBucketIds}
            onBucketChange={onBucketChange}
          />
        </div>
      }
    >
      <SidebarItemList
        items={plans}
        activeId={activePlanId}
        emptyMessage="No saved plans yet"
        deleteTitle="Delete plan?"
        deleteDescription={(p) => `This will permanently delete "${displayLabel(p) || "this plan"}".`}
        getLabel={displayLabel}
        getTime={(p) => p.created_at}
        renderIcon={(p) =>
          isAgentPlan(p) ? (
            <Bot className="h-3 w-3 shrink-0 text-muted-foreground" />
          ) : (
            <Lightbulb className="h-3 w-3 shrink-0 text-muted-foreground" />
          )
        }
        onSelect={(p) => onLoadPlan(p.id)}
        onRename={onRenamePlan}
        onDelete={onDeletePlan}
      />
    </AppSidebar>
  )
}
