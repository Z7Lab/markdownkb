import { AppSidebar } from "@/components/ui/app-sidebar"
import { ScopePicker } from "@/components/scope-picker"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { WordCloud } from "./word-cloud"
import { RefreshCw, Search, X } from "lucide-react"
import type { Scope } from "@/lib/types"

export function GraphSidebar({
  scopes,
  selectedScopeId,
  onScopeChange,
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
}: {
  scopes: Scope[]
  selectedScopeId: string | null
  onScopeChange: (id: string | null) => void
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
}) {
  return (
    <AppSidebar
      header={
        <div className="space-y-3">
          <ScopePicker
            scopes={scopes}
            value={selectedScopeId}
            onChange={onScopeChange}
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
              min={0.5}
              max={1}
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
        </div>
      }
    >
      {wordCloudsEnabled && (
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
    </AppSidebar>
  )
}
