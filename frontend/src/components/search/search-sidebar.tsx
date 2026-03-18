import { Button } from "@/components/ui/button"
import { AppSidebar } from "@/components/ui/app-sidebar"
import { SidebarItemList } from "@/components/ui/sidebar-item-list"
import { Bot, Plus, Search, FolderOpen, Tag } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { SavedSearch, Scope } from "@/lib/types"
import { ScopeTagFilter } from "@/components/scope-tag-filter"

export function SearchSidebar({
  searches,
  activeSearchId,
  folders,
  tags,
  scopes,
  selectedFolder,
  selectedTag,
  selectedScopeIds,
  onNewSearch,
  onLoadSearch,
  onRenameSearch,
  onDeleteSearch,
  onFolderChange,
  onTagChange,
  onScopeChange,
  availableTags,
  selectedAdHocTags,
  onAdHocTagChange,
}: {
  searches: SavedSearch[]
  activeSearchId: string | null
  folders: string[]
  tags: string[]
  scopes: Scope[]
  selectedFolder: string | null
  selectedTag: string | null
  selectedScopeIds: Set<string>
  onNewSearch: () => void
  onLoadSearch: (search: SavedSearch) => void
  onRenameSearch: (id: string, query: string) => void
  onDeleteSearch: (id: string) => void
  onFolderChange: (folder: string | null) => void
  onTagChange: (tag: string | null) => void
  onScopeChange: (ids: Set<string>) => void
  availableTags: string[]
  selectedAdHocTags: Set<string>
  onAdHocTagChange: (tags: Set<string>) => void
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
            <div className="flex items-center gap-2 px-1">
              <FolderOpen className="h-3.5 w-3.5 text-muted-foreground" />
              <Select
                value={selectedFolder ?? "_all"}
                onValueChange={(v) => onFolderChange(v === "_all" ? null : v)}
              >
                <SelectTrigger className="h-8 text-xs flex-1">
                  <SelectValue placeholder="Folder" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">(all folders)</SelectItem>
                  {folders.map((f) => (
                    <SelectItem key={f} value={f}>
                      {f}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2 px-1">
              <Tag className="h-3.5 w-3.5 text-muted-foreground" />
              <Select
                value={selectedTag ?? "_all"}
                onValueChange={(v) => onTagChange(v === "_all" ? null : v)}
              >
                <SelectTrigger className="h-8 text-xs flex-1">
                  <SelectValue placeholder="Tag" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">(all tags)</SelectItem>
                  {tags.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <ScopeTagFilter
              scopes={scopes}
              selectedScopeIds={selectedScopeIds}
              onScopeChange={onScopeChange}
              availableTags={availableTags}
              selectedTags={selectedAdHocTags}
              onTagChange={onAdHocTagChange}
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
