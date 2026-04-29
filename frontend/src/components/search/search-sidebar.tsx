import { Button } from "@/components/ui/button"
import { AppSidebar } from "@/components/ui/app-sidebar"
import { SidebarItemList } from "@/components/ui/sidebar-item-list"
import { Bot, Plus, Search } from "lucide-react"
import type { SavedSearch, Scope } from "@/lib/types"
import type { Bucket } from "@/hooks/use-buckets"
import { FilterPicker } from "@/components/filter-picker"

export function SearchSidebar({
  searches,
  activeSearchId,
  scopes,
  selectedScopeIds,
  onNewSearch,
  onLoadSearch,
  onRenameSearch,
  onDeleteSearch,
  onScopeChange,
  availableTags,
  selectedAdHocTags,
  onAdHocTagChange,
  buckets,
  selectedBucketIds,
  onBucketChange,
}: {
  searches: SavedSearch[]
  activeSearchId: string | null
  scopes: Scope[]
  selectedScopeIds: Set<string>
  onNewSearch: () => void
  onLoadSearch: (search: SavedSearch) => void
  onRenameSearch: (id: string, query: string) => void
  onDeleteSearch: (id: string) => void
  onScopeChange: (ids: Set<string>) => void
  availableTags: string[]
  selectedAdHocTags: Set<string>
  onAdHocTagChange: (tags: Set<string>) => void
  buckets: Bucket[]
  selectedBucketIds: Set<string>
  onBucketChange: (ids: Set<string>) => void
}) {
  return (
    <AppSidebar
      header={
        <div className="space-y-2">
          <Button
            onClick={onNewSearch}
            variant="outline"
            className="w-full justify-start gap-2"
          >
            <Plus className="h-4 w-4" />
            New Search
          </Button>

          <FilterPicker
            scopes={scopes}
            selectedScopeIds={selectedScopeIds}
            onScopeChange={onScopeChange}
            availableTags={availableTags}
            selectedTags={selectedAdHocTags}
            onTagChange={onAdHocTagChange}
            buckets={buckets}
            selectedBucketIds={selectedBucketIds}
            onBucketChange={onBucketChange}
          />
        </div>
      }
    >
      <SidebarItemList
        items={searches}
        activeId={activeSearchId}
        emptyMessage="No search history yet"
        deleteTitle="Delete search?"
        deleteDescription={(s) => `This will permanently delete the search "${s.query || "this search"}".`}
        getLabel={(s) => s.query}
        getTime={(s) => s.created_at}
        renderIcon={(s) =>
          s.source === "agent" ? (
            <Bot className="h-3 w-3 shrink-0 text-muted-foreground" />
          ) : (
            <Search className="h-3 w-3 shrink-0 text-muted-foreground" />
          )
        }
        onSelect={onLoadSearch}
        onRename={onRenameSearch}
        onDelete={onDeleteSearch}
      />
    </AppSidebar>
  )
}
