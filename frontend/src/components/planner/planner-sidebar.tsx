import { useState } from "react"
import { Button } from "@/components/ui/button"
import { AppSidebar } from "@/components/ui/app-sidebar"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
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
  const [pendingDelete, setPendingDelete] = useState<SavedPlan | null>(null)

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
      <div className="p-3 space-y-1" role="list">
        {plans.length === 0 ? (
          <p className="text-xs text-muted-foreground px-3 py-4 text-center">
            No saved plans yet
          </p>
        ) : (
          plans.map((p) => (
            <button
              key={p.id}
              type="button"
              role="listitem"
              className={cn(
                "w-full text-left rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                activePlanId === p.id && "bg-accent border-l-2 border-l-primary",
              )}
              onClick={() => onLoadPlan(p.id)}
            >
              <Tooltip>
                <TooltipTrigger asChild>
                  <p className="font-medium overflow-hidden line-clamp-2">
                    {p.query || p.title}
                  </p>
                </TooltipTrigger>
                <TooltipContent side="right" className="max-w-sm">
                  <p>{p.query || p.title}</p>
                </TooltipContent>
              </Tooltip>
              <div className="flex items-center gap-1 mt-0.5">
                <p className="text-xs text-muted-foreground flex-1 truncate">
                  {relativeTime(p.created_at)}
                </p>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Delete plan"
                  className="h-5 w-5 shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation()
                    setPendingDelete(p)
                  }}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            </button>
          ))
        )}
      </div>
      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(open) => { if (!open) setPendingDelete(null) }}
        title="Delete plan?"
        description={`This will permanently delete "${pendingDelete?.query || pendingDelete?.title || "this plan"}".`}
        confirmLabel="Delete"
        onConfirm={() => {
          if (pendingDelete) onDeletePlan(pendingDelete.id)
          setPendingDelete(null)
        }}
      />
    </AppSidebar>
  )
}
