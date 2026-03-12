import { useState, useEffect } from "react"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Info, Save, RotateCcw } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface RetrievalSettingsFormProps {
  topK: number
  defaultTopK: number
  scoreThreshold: number
  defaultScoreThreshold: number
  hybridSearch: boolean
  defaultHybridSearch: boolean
  bm25Weight: number
  defaultBm25Weight: number
  onSave: (settings: {
    top_k: number
    score_threshold: number
    hybrid_search: boolean
    bm25_weight: number
  }) => Promise<void>
}

export function RetrievalSettingsForm({
  topK,
  defaultTopK,
  scoreThreshold,
  defaultScoreThreshold,
  hybridSearch,
  defaultHybridSearch,
  bm25Weight,
  defaultBm25Weight,
  onSave,
}: RetrievalSettingsFormProps) {
  const [topKValue, setTopKValue] = useState(topK)
  const [scoreThresholdValue, setScoreThresholdValue] = useState(scoreThreshold)
  const [hybridSearchValue, setHybridSearchValue] = useState(hybridSearch)
  const [bm25WeightValue, setBm25WeightValue] = useState(bm25Weight)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState("")

  useEffect(() => {
    setTopKValue(topK)
    setScoreThresholdValue(scoreThreshold)
    setHybridSearchValue(hybridSearch)
    setBm25WeightValue(bm25Weight)
  }, [topK, scoreThreshold, hybridSearch, bm25Weight])

  const hasChanges =
    topKValue !== topK ||
    scoreThresholdValue !== scoreThreshold ||
    hybridSearchValue !== hybridSearch ||
    bm25WeightValue !== bm25Weight

  async function handleSave() {
    setSaving(true)
    setStatus("")
    try {
      await onSave({
        top_k: topKValue,
        score_threshold: scoreThresholdValue,
        hybrid_search: hybridSearchValue,
        bm25_weight: bm25WeightValue,
      })
      setStatus("Saved")
      setTimeout(() => setStatus(""), 2000)
    } catch (err) {
      setStatus(`Error saving: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  function handleRestore() {
    setTopKValue(defaultTopK)
    setScoreThresholdValue(defaultScoreThreshold)
    setHybridSearchValue(defaultHybridSearch)
    setBm25WeightValue(defaultBm25Weight)
  }

  return (
    <div className="border-t pt-6">
      <h3 className="text-base font-semibold mb-3">Retrieval Settings</h3>
      <p className="text-sm text-muted-foreground mb-4">
        Configure hybrid search, relevance thresholds, and result limits
      </p>

      <div className="space-y-6">
        {/* Hybrid Search Toggle */}
        <div className="flex items-center justify-between p-4 border rounded-lg">
          <div className="flex items-start gap-3 flex-1">
            <div className="flex-1 space-y-1">
              <div className="flex items-center gap-2">
                <Label htmlFor="hybrid-search" className="text-sm font-medium">
                  Hybrid Search (BM25 + Vector)
                </Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-4 w-4 text-muted-foreground cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p>
                      Combine keyword matching (BM25) with semantic similarity (vector embeddings).
                      Helps prevent false positives like "ENS" matching "intensional".
                    </p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <p className="text-sm text-muted-foreground">
                Require actual keyword presence in results
              </p>
            </div>
          </div>
          <Switch
            id="hybrid-search"
            checked={hybridSearchValue}
            onCheckedChange={setHybridSearchValue}
          />
        </div>

        {/* BM25 Weight Slider */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Label className="text-sm font-medium">
                BM25 Weight: {bm25WeightValue.toFixed(2)}
              </Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-muted-foreground cursor-help" />
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">
                  <p>
                    Balance between keyword matching ({bm25WeightValue.toFixed(2)}) and
                    semantic similarity ({(1 - bm25WeightValue).toFixed(2)}).
                    Higher values favor exact keyword matches.
                  </p>
                </TooltipContent>
              </Tooltip>
            </div>
            <span className="text-xs text-muted-foreground">
              Vector: {(1 - bm25WeightValue).toFixed(2)}
            </span>
          </div>
          <Slider
            value={[bm25WeightValue]}
            onValueChange={([val]) => setBm25WeightValue(val)}
            min={0}
            max={1}
            step={0.05}
            disabled={!hybridSearchValue}
            className="w-full"
          />
        </div>

        {/* Score Threshold Slider */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Label className="text-sm font-medium">
              Minimum Relevance: {(scoreThresholdValue * 100).toFixed(0)}%
            </Label>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-4 w-4 text-muted-foreground cursor-help" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p>
                  Filter out results below this relevance score.
                  Higher values show only highly relevant results.
                </p>
              </TooltipContent>
            </Tooltip>
          </div>
          <Slider
            value={[scoreThresholdValue]}
            onValueChange={([val]) => setScoreThresholdValue(val)}
            min={0}
            max={1}
            step={0.05}
            className="w-full"
          />
        </div>

        {/* Top K Slider */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Label className="text-sm font-medium">
              Results per Search: {topKValue}
            </Label>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-4 w-4 text-muted-foreground cursor-help" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p>
                  Maximum number of results to return per search query.
                </p>
              </TooltipContent>
            </Tooltip>
          </div>
          <Slider
            value={[topKValue]}
            onValueChange={([val]) => setTopKValue(val)}
            min={1}
            max={50}
            step={1}
            className="w-full"
          />
        </div>

        {/* Save/Restore Buttons */}
        <div className="flex items-center gap-2 pt-2">
          <Button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            size="sm"
          >
            <Save className="h-3.5 w-3.5 mr-1.5" />
            {saving ? "Saving..." : "Save"}
          </Button>
          <Button
            onClick={handleRestore}
            variant="outline"
            size="sm"
          >
            <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
            Restore to Default
          </Button>
          {status && (
            <span className="text-sm text-muted-foreground">{status}</span>
          )}
        </div>
      </div>
    </div>
  )
}
