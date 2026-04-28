import { Button } from "@/components/ui/button"
import { DownloadButtons } from "@/components/ui/download-buttons"
import { Eraser, FastForward } from "lucide-react"

export function ChatControls({
  onClear,
  onContinue,
  content,
  filename,
  hasMessages,
}: {
  onClear: () => void
  onContinue: () => void
  content: string | (() => string)
  filename: string
  hasMessages: boolean
}) {
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
      <DownloadButtons content={content} filename={filename} disabled={!hasMessages} />
    </div>
  )
}
