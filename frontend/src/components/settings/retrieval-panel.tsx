import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Info } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { RetrievalSettingsForm } from "./retrieval-settings-form"
import { SearchSummaryPromptForm } from "./search-summary-prompt-form"

interface SearchPanelProps {
  intelligentSearchEnabled: boolean
  searchSummaryPrompt: string
  defaultSearchSummaryPrompt: string
  topK: number
  defaultTopK: number
  scoreThreshold: number
  defaultScoreThreshold: number
  hybridSearch: boolean
  defaultHybridSearch: boolean
  bm25Weight: number
  defaultBm25Weight: number
  onToggle: (enabled: boolean) => void
  onSavePrompt: (prompt: string) => Promise<void>
  onSaveRetrievalSettings: (settings: {
    top_k: number
    score_threshold: number
    hybrid_search: boolean
    bm25_weight: number
  }) => Promise<void>
}

export function SearchPanel({
  intelligentSearchEnabled,
  searchSummaryPrompt,
  defaultSearchSummaryPrompt,
  topK,
  defaultTopK,
  scoreThreshold,
  defaultScoreThreshold,
  hybridSearch,
  defaultHybridSearch,
  bm25Weight,
  defaultBm25Weight,
  onToggle,
  onSavePrompt,
  onSaveRetrievalSettings,
}: SearchPanelProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Retrieval Settings</h2>
        <p className="text-sm text-muted-foreground">
          Configure intelligent search, hybrid retrieval, and relevance tuning
        </p>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between p-4 border rounded-lg">
          <div className="flex items-start gap-3 flex-1">
            <div className="flex-1 space-y-1">
              <div className="flex items-center gap-2">
                <Label htmlFor="intelligent-search" className="text-base font-medium">
                  Intelligent Search
                </Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-muted-foreground cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p>
                      Use LLM to enhance search queries by extracting keywords,
                      expanding acronyms, and identifying context.
                      Improves accuracy for technical terms and specific entities.
                      Requires LLM to be available.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <p className="text-sm text-muted-foreground">
                Pre-process queries with AI to extract keywords and expand acronyms
              </p>
            </div>
          </div>
          <Switch
            id="intelligent-search"
            checked={intelligentSearchEnabled}
            onCheckedChange={onToggle}
          />
        </div>

        <div className="rounded-lg bg-muted/50 p-4 space-y-2">
          <h3 className="text-sm font-medium">How it works</h3>
          <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
            <li>Extracts critical keywords (e.g., "ENS" from your query)</li>
            <li>Expands acronyms (e.g., ENS → Ethereum Name Service)</li>
            <li>Identifies semantic context for better matching</li>
            <li>Falls back to regular search if LLM is offline</li>
          </ul>
        </div>
      </div>

      <RetrievalSettingsForm
        topK={topK}
        defaultTopK={defaultTopK}
        scoreThreshold={scoreThreshold}
        defaultScoreThreshold={defaultScoreThreshold}
        hybridSearch={hybridSearch}
        defaultHybridSearch={defaultHybridSearch}
        bm25Weight={bm25Weight}
        defaultBm25Weight={defaultBm25Weight}
        onSave={onSaveRetrievalSettings}
      />

      <SearchSummaryPromptForm
        searchSummaryPrompt={searchSummaryPrompt}
        defaultSearchSummaryPrompt={defaultSearchSummaryPrompt}
        onSave={onSavePrompt}
      />
    </div>
  )
}
