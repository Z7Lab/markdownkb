import { HardDriveDownload, Loader2 } from "lucide-react"
import { useIndexEvents } from "@/hooks/use-index-events"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

export function IndexActivityIndicator() {
  const { isIndexing, errorCount } = useIndexEvents()

  if (!isIndexing && errorCount === 0) return null

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted/50">
          {isIndexing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
          ) : (
            <HardDriveDownload className="h-3.5 w-3.5 text-muted-foreground" />
          )}
          {errorCount > 0 && (
            <span className={cn(
              "text-xs font-medium tabular-nums",
              "text-error",
            )}>
              {errorCount}
            </span>
          )}
        </div>
      </TooltipTrigger>
      <TooltipContent>
        {isIndexing && <p>Indexing files...</p>}
        {errorCount > 0 && (
          <p>{errorCount} index error{errorCount > 1 ? "s" : ""}</p>
        )}
      </TooltipContent>
    </Tooltip>
  )
}
