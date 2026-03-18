import { Button } from "@/components/ui/button"
import { AppSidebar } from "@/components/ui/app-sidebar"
import { SidebarItemList } from "@/components/ui/sidebar-item-list"
import { Plus } from "lucide-react"
import type { SavedPlan, Scope } from "@/lib/types"
import { ScopeTagFilter } from "@/components/scope-tag-filter"

export function PlannerSidebar({
  plans,
  activePlanId,
  scopes,
  selectedScopeIds,
  onScopeChange,
  availableTags,
  selectedTags,
  onTagChange,
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
  onNewPlan: () => void
  onLoadPlan: (planId: string) => void
  onRenamePlan: (planId: string, title: string) => void
  onDeletePlan: (planId: string) => void
}) {
  return (
    <AppSidebar
      header={
        <div className="space-y-2">
          <ScopeTagFilter
            scopes={scopes}
            selectedScopeIds={selectedScopeIds}
            onScopeChange={onScopeChange}
            availableTags={availableTags}
            selectedTags={selectedTags}
            onTagChange={onTagChange}
          />
          <Button
            onClick={onNewPlan}
            variant="outline"
            className="w-full justify-start gap-2"
          >
            <Plus className="h-4 w-4" />
            New Plan
          </Button>
        </div>
      }
    >
      <SidebarItemList
        items={plans}
        activeId={activePlanId}
        emptyMessage="No saved plans yet"
        deleteTitle="Delete plan?"
        deleteDescription={(p) => `This will permanently delete "${p.query || p.title || "this plan"}".`}
        getLabel={(p) => p.query || p.title}
        getTime={(p) => p.created_at}
        onSelect={(p) => onLoadPlan(p.id)}
        onRename={onRenamePlan}
        onDelete={onDeletePlan}
      />
    </AppSidebar>
  )
}
