import { useMemo } from "react"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import { SidebarSection } from "@/components/ui/sidebar-section"
import { Layers, Tag } from "lucide-react"
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
  const noScopesSelected = selectedScopeIds.size === 0

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

  const scopeSummary = useMemo(() => {
    if (selectedScopeIds.size === 0) return undefined
    const names = scopes
      .filter((s) => selectedScopeIds.has(s.id))
      .map((s) => s.name)
    return names.join(", ")
  }, [scopes, selectedScopeIds])

  const tagSummary = useMemo(() => {
    if (selectedTags.size === 0) return undefined
    return Array.from(selectedTags).join(", ")
  }, [selectedTags])

  return (
    <div className="space-y-2">
      {/* Scopes section */}
      <SidebarSection
        icon={Layers}
        label="Scopes"
        count={selectedScopeIds.size}
        summary={scopeSummary}
      >
        {scopes.length === 0 ? (
          <p className="text-[10px] text-muted-foreground pl-5">
            No scopes — create in Settings
          </p>
        ) : (
          <div className="space-y-0.5 pl-2">
            <label className="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent cursor-pointer text-xs">
              <Checkbox
                checked={noScopesSelected}
                onCheckedChange={() => onScopeChange(new Set())}
              />
              <span className={noScopesSelected ? "text-foreground" : "text-muted-foreground"}>
                All sources
              </span>
            </label>
            {scopes.map((s) => (
              <label
                key={s.id}
                className="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent cursor-pointer text-xs"
              >
                <Checkbox
                  checked={selectedScopeIds.has(s.id)}
                  onCheckedChange={() => toggleScope(s.id)}
                />
                <span className="truncate flex-1">{s.name}</span>
                {s.exclude_patterns.length > 0 && (
                  <span className="text-[10px] text-destructive/60 shrink-0" title={`Excludes: ${s.exclude_patterns.join(", ")}`}>
                    {s.exclude_patterns.length} excl.
                  </span>
                )}
              </label>
            ))}
          </div>
        )}
      </SidebarSection>

      {/* Ad-hoc tags section */}
      {availableTags.length > 0 && (
        <SidebarSection
          icon={Tag}
          label="Markdown Tags"
          count={selectedTags.size}
          summary={tagSummary}
        >
          <ScrollArea
            className="pl-2"
            style={{ height: Math.min(availableTags.length * 28 + (selectedTags.size > 0 ? 24 : 0), 168) }}
          >
            <div className="space-y-0.5">
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
          </ScrollArea>
        </SidebarSection>
      )}
    </div>
  )
}
