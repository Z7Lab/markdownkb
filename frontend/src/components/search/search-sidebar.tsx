import { Button } from "@/components/ui/button"
import { AppSidebar } from "@/components/ui/app-sidebar"
import { Plus, Search, Trash2 } from "lucide-react"
import type { SavedSearch } from "@/lib/types"
import { cn, relativeTime } from "@/lib/utils"

export function SearchSidebar({
  searches,
  activeSearchId,
  onNewSearch,
  onLoadSearch,
  onDeleteSearch,
}: {
  searches: SavedSearch[]
  activeSearchId: string | null
  onNewSearch: () => void
  onLoadSearch: (search: SavedSearch) => void
  onDeleteSearch: (id: string) => void
}) {
  return (
    <AppSidebar
      header={
        <Button
          onClick={onNewSearch}
          variant="outline"
          className="w-full justify-start gap-2"
        >
          <Plus className="h-4 w-4" />
          New Search
        </Button>
      }
    >
      <div className="p-3 space-y-1" role="list">
        {searches.map((s) => (
          <button
            key={s.id}
            type="button"
            role="listitem"
            className={cn(
              "w-full text-left rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              activeSearchId === s.id && "bg-accent border-l-2 border-l-primary",
            )}
            onClick={() => onLoadSearch(s)}
          >
            <div className="flex items-center gap-1.5 mb-0.5">
              <Search className="h-3 w-3 shrink-0 text-muted-foreground" />
              <p className="font-medium overflow-hidden line-clamp-2 flex-1">
                {s.query}
              </p>
            </div>
            <div className="flex items-center gap-1">
              <p className="text-xs text-muted-foreground flex-1 truncate">
                {relativeTime(s.created_at)}
                {s.folder && ` · ${s.folder.split("/").pop()}`}
              </p>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Delete search"
                className="h-5 w-5 shrink-0 text-muted-foreground hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation()
                  onDeleteSearch(s.id)
                }}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          </button>
        ))}
        {searches.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">
            No search history yet
          </p>
        )}
      </div>
    </AppSidebar>
  )
}
