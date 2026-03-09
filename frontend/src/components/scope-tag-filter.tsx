import { useState } from "react"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { Layers, Tag, FolderCog, ChevronDown, ChevronRight } from "lucide-react"
import type { Scope } from "@/lib/types"

export function ScopeTagFilter({
  scopes,
  selectedScopeIds,
  onScopeChange,
  availableTags,
  selectedTags,
  onTagChange,
}: {
  scopes: Scope[]
  selectedScopeIds: Set<string>
  onScopeChange: (ids: Set<string>) => void
  availableTags: string[]
  selectedTags: Set<string>
  onTagChange: (tags: Set<string>) => void
}) {
  const [scopesOpen, setScopesOpen] = useState(true)
  const [tagsOpen, setTagsOpen] = useState(true)

  const allScopesSelected = scopes.length > 0 && selectedScopeIds.size === scopes.length
  const noScopesSelected = selectedScopeIds.size === 0

  function toggleAllScopes() {
    if (allScopesSelected) {
      onScopeChange(new Set())
    } else {
      onScopeChange(new Set(scopes.map((s) => s.id)))
    }
  }

  function toggleScope(id: string) {
    const next = new Set(selectedScopeIds)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onScopeChange(next)
  }

  function toggleTag(tag: string) {
    const next = new Set(selectedTags)
    if (next.has(tag)) next.delete(tag)
    else next.add(tag)
    onTagChange(next)
  }

  function clearTags() {
    onTagChange(new Set())
  }

  return (
    <div className="space-y-2">
      {/* Scopes section */}
      <div className="space-y-1 px-1">
        <button
          className="flex items-center gap-2 w-full text-left"
          onClick={() => setScopesOpen(!scopesOpen)}
        >
          {scopesOpen ? (
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3 w-3 text-muted-foreground" />
          )}
          <Layers className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-xs font-medium text-muted-foreground">Scopes</span>
          {!noScopesSelected && (
            <Badge variant="secondary" className="text-[10px] h-4 px-1 ml-auto">
              {selectedScopeIds.size}
            </Badge>
          )}
        </button>

        {scopesOpen && (
          scopes.length === 0 ? (
            <p className="text-[10px] text-muted-foreground pl-5">
              No scopes — create in Settings
            </p>
          ) : (
            <div className="space-y-0.5 pl-2">
              <label className="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent cursor-pointer text-xs">
                <Checkbox
                  checked={allScopesSelected}
                  onCheckedChange={toggleAllScopes}
                />
                <span className={noScopesSelected ? "text-foreground" : "text-muted-foreground"}>
                  {noScopesSelected ? "All sources" : "Select all"}
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
                      checked={selectedScopeIds.has(s.id)}
                      onCheckedChange={() => toggleScope(s.id)}
                    />
                    <span className="truncate flex-1">{s.name}</span>
                    {hasFolders && (
                      <FolderCog className="h-2.5 w-2.5 text-muted-foreground shrink-0" />
                    )}
                    {hasTags && (
                      <Tag className="h-2.5 w-2.5 text-muted-foreground shrink-0" />
                    )}
                  </label>
                )
              })}
            </div>
          )
        )}
      </div>

      {/* Ad-hoc tags section */}
      {availableTags.length > 0 && (
        <div className="space-y-1 px-1">
          <button
            className="flex items-center gap-2 w-full text-left"
            onClick={() => setTagsOpen(!tagsOpen)}
          >
            {tagsOpen ? (
              <ChevronDown className="h-3 w-3 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-3 w-3 text-muted-foreground" />
            )}
            <Tag className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="text-xs font-medium text-muted-foreground">Tags</span>
            {selectedTags.size > 0 && (
              <Badge variant="secondary" className="text-[10px] h-4 px-1 ml-auto">
                {selectedTags.size}
              </Badge>
            )}
          </button>

          {tagsOpen && (
            <div className="space-y-0.5 pl-2">
              {selectedTags.size > 0 && (
                <button
                  className="text-[10px] text-muted-foreground hover:text-foreground px-1 py-0.5"
                  onClick={clearTags}
                >
                  Clear all
                </button>
              )}
              {availableTags.map((tag) => (
                <label
                  key={tag}
                  className="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent cursor-pointer text-xs"
                >
                  <Checkbox
                    checked={selectedTags.has(tag)}
                    onCheckedChange={() => toggleTag(tag)}
                  />
                  <span className="truncate">{tag}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
