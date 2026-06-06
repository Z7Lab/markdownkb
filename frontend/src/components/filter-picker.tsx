import { useMemo, useState } from "react"
import { Archive, Layers, SlidersHorizontal, Tag } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { Scope } from "@/lib/types"
import type { Bucket } from "@/hooks/use-buckets"

export function FilterPicker({
  scopes,
  selectedScopeIds,
  onScopeChange,
  availableTags,
  selectedTags,
  onTagChange,
  buckets,
  selectedBucketIds,
  onBucketChange,
}: {
  scopes: Scope[]
  selectedScopeIds: Set<string>
  onScopeChange: (ids: Set<string>) => void
  availableTags: string[]
  selectedTags: Set<string>
  onTagChange: (tags: Set<string>) => void
  buckets: Bucket[]
  selectedBucketIds: Set<string>
  onBucketChange: (ids: Set<string>) => void
}) {
  const [open, setOpen] = useState(false)

  const activeBuckets = buckets.filter((b) => !b.expired && !b.hidden)
  const noScopesSelected = selectedScopeIds.size === 0
  const hasBucket = selectedBucketIds.size > 0

  const { summaryText, activeCount } = useMemo(() => {
    const parts: string[] = []

    if (selectedScopeIds.size === 1) {
      const name = scopes.find((s) => selectedScopeIds.has(s.id))?.name
      if (name) parts.push(name)
    } else if (selectedScopeIds.size > 1) {
      parts.push(`${selectedScopeIds.size} scopes`)
    }

    if (selectedTags.size === 1) {
      parts.push(Array.from(selectedTags)[0]!)
    } else if (selectedTags.size > 1) {
      parts.push(`${selectedTags.size} tags`)
    }

    const activeBucketNames = activeBuckets.filter((b) => selectedBucketIds.has(b.id))
    if (activeBucketNames.length === 1) {
      parts.push(activeBucketNames[0]!.name)
    } else if (activeBucketNames.length > 1) {
      parts.push(`${activeBucketNames.length} buckets`)
    }

    return {
      summaryText: parts.length > 0 ? parts.join(" · ") : "All sources",
      activeCount: selectedScopeIds.size + selectedTags.size + selectedBucketIds.size,
    }
  }, [scopes, selectedScopeIds, selectedTags, activeBuckets, selectedBucketIds])

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

  function toggleBucket(id: string, checked: boolean) {
    const next = new Set(selectedBucketIds)
    if (checked) next.add(id)
    else next.delete(id)
    onBucketChange(next)
  }

  function tabBadge(count: number) {
    if (count === 0) return null
    return (
      <span className="text-[10px] font-semibold bg-primary text-primary-foreground px-1 py-0.5 rounded-full leading-tight">
        {count}
      </span>
    )
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md border border-input bg-background hover:bg-accent text-xs transition-colors text-left"
      >
        <SlidersHorizontal className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className={`flex-1 truncate ${activeCount > 0 ? "text-foreground" : "text-muted-foreground"}`}>
          {summaryText}
        </span>
        {activeCount > 0 && (
          <span className="shrink-0 text-[10px] font-semibold bg-primary text-primary-foreground px-1.5 py-0.5 rounded-full leading-tight">
            {activeCount}
          </span>
        )}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-sm p-6">
          <DialogHeader>
            <DialogTitle className="text-sm">Filters</DialogTitle>
          </DialogHeader>

          <Tabs defaultValue="scopes">
            <TabsList className="w-full">
              <TabsTrigger value="scopes" className="flex-1 gap-1">
                <Layers className="h-3.5 w-3.5" />
                Scopes
                {tabBadge(selectedScopeIds.size)}
              </TabsTrigger>
              <TabsTrigger value="tags" className="flex-1 gap-1">
                <Tag className="h-3.5 w-3.5" />
                Tags
                {tabBadge(selectedTags.size)}
              </TabsTrigger>
              <TabsTrigger value="buckets" className="flex-1 gap-1">
                <Archive className="h-3.5 w-3.5" />
                Buckets
                {tabBadge(selectedBucketIds.size)}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="scopes" className="mt-3 space-y-0.5">
              {scopes.length === 0 ? (
                <p className="text-[10px] text-muted-foreground px-1 py-2">No scopes — create in Settings</p>
              ) : (
                <>
                  <div className="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent text-xs">
                    <Checkbox
                      id="filter-scope-all"
                      checked={noScopesSelected}
                      onCheckedChange={() => onScopeChange(new Set())}
                    />
                    <label htmlFor="filter-scope-all" className="cursor-pointer flex-1">
                      {noScopesSelected && hasBucket ? "Bucket only" : "All sources"}
                    </label>
                    {noScopesSelected && hasBucket && (
                      <span className="text-[10px] text-muted-foreground/60 shrink-0">no scope active</span>
                    )}
                  </div>
                  {scopes.map((s) => (
                    <div key={s.id} className="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent text-xs">
                      <Checkbox
                        id={`filter-scope-${s.id}`}
                        checked={selectedScopeIds.has(s.id)}
                        onCheckedChange={() => toggleScope(s.id)}
                      />
                      <label htmlFor={`filter-scope-${s.id}`} className="cursor-pointer truncate flex-1">
                        {s.name}
                      </label>
                      {s.exclude_patterns.length > 0 && (
                        <span
                          className="text-[10px] text-destructive/60 shrink-0"
                          title={`Excludes: ${s.exclude_patterns.join(", ")}`}
                        >
                          {s.exclude_patterns.length} excl.
                        </span>
                      )}
                    </div>
                  ))}
                </>
              )}
            </TabsContent>

            <TabsContent value="tags" className="mt-3">
              {availableTags.length === 0 ? (
                <p className="text-[10px] text-muted-foreground px-1 py-2">No tags found in your documents</p>
              ) : (
                <>
                  {selectedTags.size > 0 && (
                    <button
                      className="text-[10px] text-muted-foreground hover:text-foreground px-1 pb-1"
                      onClick={() => onTagChange(new Set())}
                    >
                      Clear all
                    </button>
                  )}
                  <ScrollArea style={{ height: Math.min(availableTags.length * 30, 300) }}>
                    <div className="space-y-0.5">
                      {availableTags.map((tag) => (
                        <div key={tag} className="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent text-xs">
                          <Checkbox
                            id={`filter-tag-${tag}`}
                            checked={selectedTags.has(tag)}
                            onCheckedChange={() => toggleTag(tag)}
                          />
                          <label htmlFor={`filter-tag-${tag}`} className="cursor-pointer truncate flex-1">
                            {tag}
                          </label>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </>
              )}
            </TabsContent>

            <TabsContent value="buckets" className="mt-3 space-y-0.5">
              {activeBuckets.length === 0 ? (
                <p className="text-[10px] text-muted-foreground px-1 py-2">No buckets — create in the Buckets tab</p>
              ) : (
                activeBuckets.map((b) => (
                  <div key={b.id} className="flex items-center gap-2 px-1 py-1 rounded hover:bg-accent text-xs">
                    <Checkbox
                      id={`filter-bucket-${b.id}`}
                      checked={selectedBucketIds.has(b.id)}
                      onCheckedChange={(checked) => toggleBucket(b.id, !!checked)}
                    />
                    <label htmlFor={`filter-bucket-${b.id}`} className="cursor-pointer truncate flex-1">
                      {b.name}
                    </label>
                    <span className="text-[10px] text-muted-foreground shrink-0">{b.file_count} files</span>
                  </div>
                ))
              )}
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>
    </>
  )
}
