import { AppSidebar } from "@/components/ui/app-sidebar"
import { ScopeTagFilter } from "@/components/scope-tag-filter"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { WordCloud } from "./word-cloud"
import { RefreshCw, Search, Square, Wand2, X } from "lucide-react"
import type { GraphMode } from "@/hooks/use-graph"
import type { KGData, Scope } from "@/lib/types"

export function GraphSidebar({
  scopes,
  selectedScopeIds,
  onScopeChange,
  availableTags,
  selectedTags,
  onTagChange,
  threshold,
  onThresholdChange,
  spread,
  onSpreadChange,
  searchTerm,
  onSearchChange,
  onRefresh,
  isLoading,
  wordCloudsEnabled,
  onWordCloudsChange,
  activeWordCloud,
  wordCloudLabel,
  onTermClick,
  mode,
  onModeChange,
  kgData,
  extraction,
  onStartExtraction,
  onCancelExtraction,
  docmapEnabled,
  kgEnabled,
}: {
  scopes: Scope[]
  selectedScopeIds: Set<string>
  onScopeChange: (ids: Set<string>) => void
  availableTags: string[]
  selectedTags: Set<string>
  onTagChange: (tags: Set<string>) => void
  threshold: number
  onThresholdChange: (v: number) => void
  spread: number
  onSpreadChange: (v: number) => void
  searchTerm: string
  onSearchChange: (term: string) => void
  onRefresh: () => void
  isLoading: boolean
  wordCloudsEnabled: boolean
  onWordCloudsChange: (v: boolean) => void
  activeWordCloud: Record<string, number>
  wordCloudLabel: string
  onTermClick: (term: string) => void
  mode: GraphMode
  onModeChange: (mode: GraphMode) => void
  kgData: KGData | null
  extraction: { running: boolean; progress: number; message: string; result: string; files_done: number; files_total: number }
  onStartExtraction: () => void
  onCancelExtraction: () => void
  docmapEnabled: boolean
  kgEnabled: boolean
}) {
  return (
    <AppSidebar
      header={
        <div className="space-y-3">
          {/* Mode toggle — only shown when both plugins are enabled */}
          {docmapEnabled && kgEnabled && (
            <div className="flex rounded-md border overflow-hidden">
              <button
                type="button"
                className={`flex-1 text-xs py-1.5 px-2 transition-colors ${mode === "similarity" ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}
                onClick={() => onModeChange("similarity")}
              >
                Doc Map
              </button>
              <button
                type="button"
                className={`flex-1 text-xs py-1.5 px-2 transition-colors ${mode === "knowledge" ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}
                onClick={() => onModeChange("knowledge")}
              >
                Knowledge
              </button>
            </div>
          )}

          {mode === "similarity" && (
            <>
              <ScopeTagFilter
                scopes={scopes}
                selectedScopeIds={selectedScopeIds}
                onScopeChange={onScopeChange}
                availableTags={availableTags}
                selectedTags={selectedTags}
                onTagChange={onTagChange}
              />

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs text-muted-foreground">
                    Similarity: {threshold.toFixed(2)}
                  </label>
                </div>
                <Slider
                  value={[threshold]}
                  onValueChange={([v]) => onThresholdChange(v)}
                  min={0.6}
                  max={0.95}
                  step={0.05}
                  className="w-full"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs text-muted-foreground">
                    Spread: {spread.toFixed(0)}%
                  </label>
                </div>
                <Slider
                  value={[spread]}
                  onValueChange={([v]) => onSpreadChange(v)}
                  min={10}
                  max={200}
                  step={5}
                  className="w-full"
                />
              </div>

              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  placeholder="Filter by term..."
                  value={searchTerm}
                  onChange={(e) => onSearchChange(e.target.value)}
                  className="h-8 text-xs pl-8 pr-8"
                />
                {searchTerm && (
                  <button
                    onClick={() => onSearchChange("")}
                    className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>

              <div className="flex items-center justify-between">
                <label className="text-xs text-muted-foreground">Word Clouds</label>
                <Switch
                  checked={wordCloudsEnabled}
                  onCheckedChange={onWordCloudsChange}
                  aria-label="Include word clouds"
                />
              </div>

              <Button
                variant="outline"
                size="sm"
                className="w-full gap-1.5"
                onClick={onRefresh}
                disabled={isLoading}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
            </>
          )}

          {mode === "knowledge" && (
            <>
              {kgData && kgData.stats.unique_entities > 0 && (
                <div className="text-xs text-muted-foreground space-y-1">
                  <div className="flex justify-between">
                    <span>Entities</span>
                    <span className="font-medium text-foreground">{kgData.stats.unique_entities}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Relationships</span>
                    <span className="font-medium text-foreground">{kgData.stats.relationships}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Source files</span>
                    <span className="font-medium text-foreground">{kgData.stats.source_files}</span>
                  </div>
                </div>
              )}

              {kgData && kgData.entity_types.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">Entity types</p>
                  <div className="flex flex-wrap gap-1">
                    {kgData.entity_types.map((t) => (
                      <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-full border bg-muted">{t}</span>
                    ))}
                  </div>
                </div>
              )}

              {kgData && kgData.relationship_types.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">Relationship types</p>
                  <div className="flex flex-wrap gap-1">
                    {kgData.relationship_types.map((t) => (
                      <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-full border bg-muted">{t}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Extraction controls */}
              {extraction.running ? (
                <div className="space-y-2">
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all duration-300"
                      style={{ width: `${Math.max(extraction.progress * 100, 1)}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {extraction.message} ({extraction.files_done}/{extraction.files_total})
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="w-full gap-1.5"
                    onClick={onCancelExtraction}
                  >
                    <Square className="h-3 w-3" />
                    Cancel
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {extraction.result && (
                    <p className="text-xs text-muted-foreground">{extraction.result}</p>
                  )}
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1 gap-1.5"
                      onClick={onStartExtraction}
                    >
                      <Wand2 className="h-3.5 w-3.5" />
                      Extract Entities
                    </Button>
                    {kgData && kgData.stats.unique_entities > 0 && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-1.5"
                        onClick={onRefresh}
                        disabled={isLoading}
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      }
    >
      {mode === "similarity" && wordCloudsEnabled && (
        <div className="px-1 py-2">
          <p className="text-xs font-medium text-muted-foreground px-3 mb-2">
            {wordCloudLabel}
          </p>
          <WordCloud
            terms={activeWordCloud}
            activeTerm={searchTerm || undefined}
            onTermClick={onTermClick}
          />
        </div>
      )}

      {mode === "knowledge" && kgData && kgData.entities.length > 0 && (
        <div className="px-3 py-2 space-y-1">
          <p className="text-xs font-medium text-muted-foreground mb-2">
            Top entities ({kgData.entities.length})
          </p>
          {kgData.entities
            .sort((a, b) => b.mention_count - a.mention_count)
            .slice(0, 30)
            .map((e) => (
              <div key={`${e.name}::${e.entity_type}`} className="flex items-center justify-between text-xs py-0.5">
                <span className="truncate flex-1 min-w-0">{e.display_name}</span>
                <span className="text-[10px] text-muted-foreground ml-2 shrink-0">{e.entity_type}</span>
              </div>
            ))}
        </div>
      )}
    </AppSidebar>
  )
}
