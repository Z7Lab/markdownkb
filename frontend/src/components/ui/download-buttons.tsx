import { FileDown, FileCode } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { downloadMarkdown, downloadHtml } from "@/lib/utils"

export function DownloadButtons({
  content,
  filename,
  disabled,
  className,
  buttonClassName,
}: {
  content: string | (() => string)
  filename: string
  disabled?: boolean
  className?: string
  buttonClassName?: string
}) {
  function resolve() { return typeof content === "function" ? content() : content }
  return (
    <div className={cn("flex gap-2", className)}>
      <Button
        variant="outline"
        size="sm"
        disabled={disabled}
        className={buttonClassName}
        onClick={() => downloadMarkdown(resolve(), filename)}
      >
        <FileDown className="h-3.5 w-3.5 mr-1.5" />
        Save MD
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={disabled}
        className={buttonClassName}
        onClick={() => downloadHtml(resolve(), filename)}
      >
        <FileCode className="h-3.5 w-3.5 mr-1.5" />
        Save HTML
      </Button>
    </div>
  )
}
