import { useState } from "react"
import { FileDown, FileCode } from "lucide-react"
import { toast } from "sonner"
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
  content: string | (() => string | Promise<string>)
  filename: string
  disabled?: boolean
  className?: string
  buttonClassName?: string
}) {
  const [busy, setBusy] = useState(false)
  async function save(download: (text: string, name: string) => void) {
    setBusy(true)
    try {
      const text = typeof content === "function" ? await content() : content
      download(text, filename)
    } catch {
      toast.error("Failed to prepare download")
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className={cn("flex gap-2", className)}>
      <Button
        variant="outline"
        size="sm"
        disabled={disabled || busy}
        className={buttonClassName}
        onClick={() => save(downloadMarkdown)}
      >
        <FileDown className="h-3.5 w-3.5 mr-1.5" />
        Save MD
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={disabled || busy}
        className={buttonClassName}
        onClick={() => save(downloadHtml)}
      >
        <FileCode className="h-3.5 w-3.5 mr-1.5" />
        Save HTML
      </Button>
    </div>
  )
}
