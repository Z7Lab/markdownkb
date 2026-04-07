import { Button } from "@/components/ui/button"
import { AppSidebar } from "@/components/ui/app-sidebar"
import { SidebarItemList } from "@/components/ui/sidebar-item-list"
import { Bot, Plus, Search } from "lucide-react"
import type { SavedSearch, Scope } from "@/lib/types"
import type { Bucket } from "@/hooks/use-buckets"
import { ScopeTagFilter } from "@/components/scope-tag-filter"
import { BucketSelector } from "@/components/bucket-selector"

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
  selectedBucketId,
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
  selectedBucketId: string | null
  onBucketChange: (id: string | null) => void
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

          {/* Filters */}
          <div className="space-y-1.5">
            <ScopeTagFilter
              scopes={scopes}
              selectedScopeIds={selectedScopeIds}
              onScopeChange={onScopeChange}
              availableTags={availableTags}
              selectedTags={selectedAdHocTags}
              onTagChange={onAdHocTagChange}
            />

            <BucketSelector
              buckets={buckets}
              selectedBucketId={selectedBucketId}
              onBucketChange={onBucketChange}
            />
          </div>
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
        renderMeta={(s) =>
          s.folder ? <>{` · ${s.folder.split("/").pop()}`}</> : null
        }
        onSelect={onLoadSearch}
        onRename={onRenameSearch}
        onDelete={onDeleteSearch}
      />
    </AppSidebar>
  )
}
