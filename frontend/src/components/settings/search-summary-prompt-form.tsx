import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Save, RotateCcw } from "lucide-react"

interface SearchSummaryPromptFormProps {
  searchSummaryPrompt: string
  defaultSearchSummaryPrompt: string
  onSave: (prompt: string) => Promise<void>
}

export function SearchSummaryPromptForm({
  searchSummaryPrompt,
  defaultSearchSummaryPrompt,
  onSave,
}: SearchSummaryPromptFormProps) {
  const [promptValue, setPromptValue] = useState(searchSummaryPrompt || defaultSearchSummaryPrompt)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState("")

  useEffect(() => {
    if (searchSummaryPrompt) {
      setPromptValue(searchSummaryPrompt)
    }
  }, [searchSummaryPrompt])

  const hasChanges = promptValue !== (searchSummaryPrompt || defaultSearchSummaryPrompt)

  async function handleSave() {
    setSaving(true)
    setStatus("")
    try {
      await onSave(promptValue)
      setStatus("Saved")
      setTimeout(() => setStatus(""), 2000)
    } catch {
      setStatus("Error saving")
    } finally {
      setSaving(false)
    }
  }

  function handleRestore() {
    setPromptValue(defaultSearchSummaryPrompt)
  }

  return (
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
        <Button onClick={handleSave} disabled={saving || !hasChanges} size="sm">
          <Save className="h-3.5 w-3.5 mr-1.5" />
          {saving ? "Saving..." : "Save"}
        </Button>
        <Button onClick={handleRestore} variant="outline" size="sm">
          <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
          Restore to Default
        </Button>
        {status && (
          <span className="text-sm text-muted-foreground">{status}</span>
        )}
      </div>
    </div>
  )
}
