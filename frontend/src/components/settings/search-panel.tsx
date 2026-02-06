import { useState, useEffect } from "react"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Info, Save, RotateCcw } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface SearchPanelProps {
  intelligentSearchEnabled: boolean
  searchSummaryPrompt: string
  defaultSearchSummaryPrompt: string
  onToggle: (enabled: boolean) => void
  onSavePrompt: (prompt: string) => Promise<void>
}

export function SearchPanel({
  intelligentSearchEnabled,
  searchSummaryPrompt,
  defaultSearchSummaryPrompt,
  onToggle,
  onSavePrompt,
}: SearchPanelProps) {
  const [promptValue, setPromptValue] = useState(searchSummaryPrompt || defaultSearchSummaryPrompt)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState("")

  useEffect(() => {
    if (searchSummaryPrompt) {
      setPromptValue(searchSummaryPrompt)
    }
  }, [searchSummaryPrompt])

  const hasChanges = promptValue !== (searchSummaryPrompt || defaultSearchSummaryPrompt)

  async function handleSavePrompt() {
    setSaving(true)
    setStatus("")
    try {
      await onSavePrompt(promptValue)
      setStatus("Saved")
      setTimeout(() => setStatus(""), 2000)
    } catch {
      setStatus("Error saving")
    } finally {
      setSaving(false)
    }
  }

  function handleRestorePrompt() {
    setPromptValue(defaultSearchSummaryPrompt)
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Search Settings</h2>
        <p className="text-sm text-muted-foreground">
          Configure intelligent search and retrieval options
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

      <div className="border-t pt-6">
        <h3 className="text-base font-semibold mb-3">Search Summary Prompt</h3>
        <p className="text-sm text-muted-foreground mb-3">
          Customize how the AI generates search summaries and answers.
        </p>
        <Textarea
          value={promptValue}
          onChange={(e) => setPromptValue(e.target.value)}
          className="min-h-[150px] font-mono text-sm mb-3"
          placeholder="Enter search summary prompt..."
        />
        <div className="flex items-center gap-2">
          <Button onClick={handleSavePrompt} disabled={saving || !hasChanges} size="sm">
            <Save className="h-3.5 w-3.5 mr-1.5" />
            {saving ? "Saving..." : "Save"}
          </Button>
          <Button onClick={handleRestorePrompt} variant="outline" size="sm">
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
