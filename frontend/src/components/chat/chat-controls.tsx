import { Button } from "@/components/ui/button"
import { Eraser, FastForward, Save } from "lucide-react"
import { toast } from "sonner"

export function ChatControls({
  onClear,
  onContinue,
  onSavePlan,
  hasMessages,
}: {
  onClear: () => void
  onContinue: () => void
  onSavePlan: () => Promise<string>
  hasMessages: boolean
}) {
  async function handleSave() {
    const result = await onSavePlan()
    toast(result)
  }

  return (
    <div className="flex gap-2 px-4 pb-3">
      <Button variant="outline" size="sm" onClick={onClear} disabled={!hasMessages}>
        <Eraser className="h-3.5 w-3.5 mr-1.5" />
        Clear
      </Button>
      <Button variant="outline" size="sm" onClick={onContinue} disabled={!hasMessages}>
        <FastForward className="h-3.5 w-3.5 mr-1.5" />
        Continue
      </Button>
      <Button variant="outline" size="sm" onClick={handleSave} disabled={!hasMessages}>
        <Save className="h-3.5 w-3.5 mr-1.5" />
        Save Plan
      </Button>
    </div>
  )
}
