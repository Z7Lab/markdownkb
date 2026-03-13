import { useRef, useState, type KeyboardEvent } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AppSidebar } from "@/components/ui/app-sidebar"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Pencil, Plus, Trash2 } from "lucide-react"
import type { SavedPlan, Scope } from "@/lib/types"
import { cn, relativeTime } from "@/lib/utils"
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
  const [pendingDelete, setPendingDelete] = useState<SavedPlan | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  function startRename(p: SavedPlan) {
    setEditingId(p.id)
    setEditValue(p.query || p.title)
    setTimeout(() => inputRef.current?.select(), 0)
  }

  function commitRename() {
    if (editingId && editValue.trim()) {
      onRenamePlan(editingId, editValue.trim())
    }
    setEditingId(null)
  }

  function handleRenameKey(e: KeyboardEvent) {
    if (e.key === "Enter") commitRename()
    if (e.key === "Escape") setEditingId(null)
  }

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
              {editingId === p.id ? (
                <Input
                  ref={inputRef}
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={handleRenameKey}
                  onClick={(e) => e.stopPropagation()}
                  className="h-6 text-sm px-1 py-0"
                  autoFocus
                />
              ) : (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <p
                      className="font-medium overflow-hidden line-clamp-2"
                      onDoubleClick={(e) => {
                        e.stopPropagation()
                        startRename(p)
                      }}
                    >
                      {p.query || p.title}
                    </p>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-sm">
                    <p>{p.query || p.title}</p>
                  </TooltipContent>
                </Tooltip>
              )}
              <div className="flex items-center gap-1 mt-0.5">
                <p className="text-xs text-muted-foreground flex-1 truncate">
                  {relativeTime(p.created_at)}
                </p>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Rename plan"
                  className="h-5 w-5 shrink-0 text-muted-foreground hover:text-foreground"
                  onClick={(e) => {
                    e.stopPropagation()
                    startRename(p)
                  }}
                >
                  <Pencil className="h-3 w-3" />
                </Button>
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
