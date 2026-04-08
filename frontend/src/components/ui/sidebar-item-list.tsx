import { useRef, useState, type KeyboardEvent, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Pencil, Search, Trash2, X } from "lucide-react"
import { cn, relativeTime } from "@/lib/utils"

/** Minimal shape every sidebar item must satisfy. */
export interface SidebarItem {
  id: string
}

export interface SidebarItemListProps<T extends SidebarItem> {
  items: T[]
  activeId: string | null
  emptyMessage: string
  deleteTitle: string
  deleteDescription: (item: T) => string

  /** Display label for the item (used in tooltip and inline text). */
  getLabel: (item: T) => string

  /** Timestamp string for relative time display. */
  getTime: (item: T) => string

  /** Optional icon rendered before the label. */
  renderIcon?: (item: T) => ReactNode

  /** Optional extra content after the timestamp (e.g. folder badge). */
  renderMeta?: (item: T) => ReactNode

  onSelect: (item: T) => void
  onRename: (id: string, label: string) => void
  onDelete: (id: string) => void
}

export function SidebarItemList<T extends SidebarItem>({
  items,
  activeId,
  emptyMessage,
  deleteTitle,
  deleteDescription,
  getLabel,
  getTime,
  renderIcon,
  renderMeta,
  onSelect,
  onRename,
  onDelete,
}: SidebarItemListProps<T>) {
  const [pendingDelete, setPendingDelete] = useState<T | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState("")
  const [filterText, setFilterText] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  const filteredItems = filterText
    ? items.filter((item) =>
        getLabel(item).toLowerCase().includes(filterText.toLowerCase()),
      )
    : items

  function startRename(item: T) {
    setEditingId(item.id)
    setEditValue(getLabel(item))
    setTimeout(() => inputRef.current?.select(), 0)
  }

  function commitRename() {
    if (editingId && editValue.trim()) {
      onRename(editingId, editValue.trim())
    }
    setEditingId(null)
  }

  function handleRenameKey(e: KeyboardEvent) {
    if (e.key === "Enter") commitRename()
    if (e.key === "Escape") setEditingId(null)
  }

  return (
    <>
      {items.length > 1 && (
        <div className="px-3 pt-3 relative">
          <Search className="absolute left-5.5 top-5.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Filter by title..."
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            className="h-8 text-xs pl-8 pr-8"
          />
          {filterText && (
            <button
              type="button"
              onClick={() => setFilterText("")}
              className="absolute right-5 top-5 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      )}
      <div className="p-3 space-y-1" role="list">
        {filteredItems.map((item) => (
          <button
            key={item.id}
            type="button"
            role="listitem"
            className={cn(
              "w-full text-left rounded-md px-3 py-2 text-sm cursor-pointer overflow-hidden hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              activeId === item.id && "bg-accent border-l-2 border-l-primary",
            )}
            onClick={() => onSelect(item)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault()
                onSelect(item)
              }
            }}
          >
            {editingId === item.id ? (
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
              <div className="flex items-center gap-1.5 mb-0.5 min-w-0">
                {renderIcon?.(item)}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <p
                      className="font-medium overflow-hidden line-clamp-2 flex-1 min-w-0"
                      onDoubleClick={(e) => {
                        e.stopPropagation()
                        startRename(item)
                      }}
                    >
                      {getLabel(item)}
                    </p>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-sm">
                    <p>{getLabel(item)}</p>
                  </TooltipContent>
                </Tooltip>
              </div>
            )}
            <div className="flex items-center gap-1 mt-0.5 min-w-0">
              <p className="text-xs text-muted-foreground flex-1 truncate min-w-0">
                {relativeTime(getTime(item))}
                {renderMeta?.(item)}
              </p>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Rename"
                className="h-5 w-5 shrink-0 text-muted-foreground hover:text-foreground"
                onClick={(e) => {
                  e.stopPropagation()
                  startRename(item)
                }}
              >
                <Pencil className="h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Delete"
                className="h-5 w-5 shrink-0 text-muted-foreground hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation()
                  setPendingDelete(item)
                }}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          </button>
        ))}
        {filteredItems.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">
            {filterText ? "No matches" : emptyMessage}
          </p>
        )}
      </div>
      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(open) => { if (!open) setPendingDelete(null) }}
        title={deleteTitle}
        description={pendingDelete ? deleteDescription(pendingDelete) : ""}
        confirmLabel="Delete"
        onConfirm={() => {
          if (pendingDelete) onDelete(pendingDelete.id)
          setPendingDelete(null)
        }}
      />
    </>
  )
}
