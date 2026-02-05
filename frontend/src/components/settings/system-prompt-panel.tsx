import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Save, RotateCcw } from "lucide-react"

export function SystemPromptPanel({
  prompt,
  defaultPrompt,
  onSave,
}: {
  prompt: string
  defaultPrompt: string
  onSave: (prompt: string) => Promise<void>
}) {
  const [value, setValue] = useState(prompt || defaultPrompt)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState("")

  useEffect(() => {
    if (prompt) {
      setValue(prompt)
    }
  }, [prompt])

  const hasChanges = value !== (prompt || defaultPrompt)

  async function handleSave() {
    setSaving(true)
    setStatus("")
    try {
      await onSave(value)
      setStatus("Saved")
      setTimeout(() => setStatus(""), 2000)
    } catch {
      setStatus("Error saving")
    } finally {
      setSaving(false)
    }
  }

  function handleRestore() {
    setValue(defaultPrompt)
  }

  return (
    <Card className="col-span-full">
      <CardHeader>
        <CardTitle>System Prompt</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Customize the instructions given to the LLM when answering your questions.
        </p>
        <Textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="min-h-[200px] font-mono text-sm"
          placeholder="Enter system prompt..."
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
      </CardContent>
    </Card>
  )
}
