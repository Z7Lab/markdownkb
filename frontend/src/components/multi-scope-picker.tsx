import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { Layers, Tag, FolderCog } from "lucide-react"
import type { Scope } from "@/lib/types"

export function MultiScopePicker({
  scopes,
  selectedIds,
  onChange,
}: {
  scopes: Scope[]
  selectedIds: Set<string>
  onChange: (ids: Set<string>) => void
}) {
  const allSelected = scopes.length > 0 && selectedIds.size === scopes.length
  const noneSelected = selectedIds.size === 0

  function toggleAll() {
    if (allSelected) {
      onChange(new Set())
    } else {
      onChange(new Set(scopes.map((s) => s.id)))
    }
  }

  function toggle(id: string) {
    const next = new Set(selectedIds)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    onChange(next)
  }

  return (
    <div className="space-y-1.5 px-1">
      <div className="flex items-center gap-2">
        <Layers className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        <span className="text-xs font-medium text-muted-foreground">Scopes</span>
        {!noneSelected && (
          <Badge variant="secondary" className="text-[10px] h-4 px-1 ml-auto">
            {selectedIds.size}
          </Badge>
        )}
      </div>

      {scopes.length === 0 ? (
        <p className="text-[10px] text-muted-foreground pl-5">
          No scopes — create in Settings
        </p>
      ) : (
        <div className="space-y-0.5">
          <label className="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent cursor-pointer text-xs">
            <Checkbox
              checked={allSelected}
              onCheckedChange={toggleAll}
            />
            <span className={noneSelected ? "text-foreground" : "text-muted-foreground"}>
              {noneSelected ? "All sources" : "Select all"}
            </span>
          </label>

          {scopes.map((s) => {
            const hasFolders = s.folders.length > 0
            const hasTags = s.tags.length > 0
            return (
              <label
                key={s.id}
                className="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent cursor-pointer text-xs"
              >
                <Checkbox
                  checked={selectedIds.has(s.id)}
                  onCheckedChange={() => toggle(s.id)}
                />
                <span className="truncate flex-1">{s.name}</span>
                {hasFolders && !hasTags && (
                  <FolderCog className="h-2.5 w-2.5 text-muted-foreground shrink-0" />
                )}
                {hasTags && !hasFolders && (
                  <Tag className="h-2.5 w-2.5 text-muted-foreground shrink-0" />
                )}
                {hasFolders && hasTags && (
                  <>
                    <FolderCog className="h-2.5 w-2.5 text-muted-foreground shrink-0" />
                    <Tag className="h-2.5 w-2.5 text-muted-foreground shrink-0" />
                  </>
                )}
              </label>
            )
          })}
        </div>
      )}
    </div>
  )
}
