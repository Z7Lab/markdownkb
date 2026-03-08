import { Button } from "@/components/ui/button"
import { AppSidebar } from "@/components/ui/app-sidebar"
import { Plus, Trash2 } from "lucide-react"
import type { SavedPlan, Scope } from "@/lib/types"
import { cn, relativeTime } from "@/lib/utils"
import { ScopePicker } from "@/components/scope-picker"

export function PlannerSidebar({
  plans,
  activePlanId,
  scopes,
  selectedScopeId,
  onScopeChange,
  onNewPlan,
  onLoadPlan,
  onDeletePlan,
}: {
  plans: SavedPlan[]
  activePlanId: string | null
  scopes: Scope[]
  selectedScopeId: string | null
  onScopeChange: (id: string | null) => void
  onNewPlan: () => void
  onLoadPlan: (planId: string) => void
  onDeletePlan: (planId: string) => void
}) {
  return (
    <AppSidebar
      header={
        <div className="space-y-2">
          <ScopePicker
            scopes={scopes}
            value={selectedScopeId}
            onChange={onScopeChange}
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
      <div className="p-1">
        {plans.length === 0 ? (
          <p className="text-xs text-muted-foreground px-3 py-4 text-center">
            No saved plans yet
          </p>
        ) : (
          plans.map((p) => (
            <div
              key={p.id}
              className={cn(
                "group flex items-center gap-1 rounded-md px-3 py-2 cursor-pointer hover:bg-accent",
                activePlanId === p.id && "bg-accent",
              )}
              onClick={() => onLoadPlan(p.id)}
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">
                  {p.query || p.title}
                </p>
                <p className="text-xs text-muted-foreground">
                  {relativeTime(p.created_at)}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 opacity-0 group-hover:opacity-100 shrink-0"
                onClick={(e) => {
                  e.stopPropagation()
                  onDeletePlan(p.id)
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))
        )}
      </div>
    </AppSidebar>
  )
}
