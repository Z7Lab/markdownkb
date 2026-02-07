import { Button } from "@/components/ui/button"
import { AppSidebar } from "@/components/ui/app-sidebar"
import { Plus, Search, Trash2, FolderOpen, Tag } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { SavedSearch } from "@/lib/types"
import { cn, relativeTime } from "@/lib/utils"

export function SearchSidebar({
  searches,
  activeSearchId,
  folders,
  tags,
  selectedFolder,
  selectedTag,
  onNewSearch,
  onLoadSearch,
  onDeleteSearch,
  onFolderChange,
  onTagChange,
}: {
  searches: SavedSearch[]
  activeSearchId: string | null
  folders: string[]
  tags: string[]
  selectedFolder: string | null
  selectedTag: string | null
  onNewSearch: () => void
  onLoadSearch: (search: SavedSearch) => void
  onDeleteSearch: (id: string) => void
  onFolderChange: (folder: string | null) => void
  onTagChange: (tag: string | null) => void
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
          </div>
        </div>
      }
    >
      <div className="p-3 space-y-1" role="list">
        {searches.map((s) => (
          <div
            key={s.id}
            role="listitem"
            className={cn(
              "w-full text-left rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              activeSearchId === s.id && "bg-accent border-l-2 border-l-primary",
            )}
            onClick={() => onLoadSearch(s)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onLoadSearch(s)
              }
            }}
            tabIndex={0}
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
          </div>
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
