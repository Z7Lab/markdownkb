import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Plus, RefreshCw, Wand2 } from "lucide-react"

interface FileActionsProps {
  status: string
  includeInIndex: boolean
  busy?: boolean
  onToggleIndex: (checked: boolean) => void
  onIndexFile: () => void
  onReindexFile: () => void
  onExtractEntities?: () => void
  kgEnabled?: boolean
  variant?: "toggle-only" | "buttons-only" | "full"
  layout?: "row" | "column"
}

export function FileActions({
  status,
  includeInIndex,
  busy = false,
  onToggleIndex,
  onIndexFile,
  onReindexFile,
  onExtractEntities,
  kgEnabled = false,
  variant = "full",
  layout = "row",
}: FileActionsProps) {
  const isIndexed = status === "complete"
  const isNotIndexed = status === "not_indexed" || status === "pending"

  const showToggle = variant === "toggle-only" || variant === "full"
  const showButtons = variant === "buttons-only" || variant === "full"

  const containerClass = layout === "column" && variant === "full"
    ? "flex flex-col gap-3"
    : "flex gap-1"

  return (
    <div className={containerClass} onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()} role="toolbar">
      {/* Include in Index Toggle */}
      {showToggle && (
        <Tooltip>
          <TooltipTrigger asChild>
            <div className={layout === "column" ? "flex items-center justify-between p-3 border rounded-lg" : "flex items-center"}>
              {layout === "column" && (
                <span className="text-sm font-medium">Include in Index</span>
              )}
              <Switch
                checked={includeInIndex}
                disabled={busy || status === "not_indexed"}
                onCheckedChange={onToggleIndex}
              />
            </div>
          </TooltipTrigger>
          <TooltipContent>
            {status === "not_indexed"
              ? "File not yet tracked"
              : includeInIndex
                ? "File is indexed — toggle off to remove from index"
                : "File is excluded from indexing — toggle on to re-include"}
          </TooltipContent>
        </Tooltip>
      )}

      {/* Action Buttons */}
      {showButtons && (
        <div className={layout === "column" ? "flex gap-2" : "flex gap-1"}>
          {isNotIndexed && includeInIndex && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  disabled={busy}
                  onClick={onIndexFile}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Index this file now</TooltipContent>
            </Tooltip>
          )}
          {isIndexed && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  disabled={busy}
                  onClick={onReindexFile}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Re-index this file</TooltipContent>
            </Tooltip>
          )}
          {kgEnabled && isIndexed && onExtractEntities && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  disabled={busy}
                  onClick={onExtractEntities}
                >
                  <Wand2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Extract entities</TooltipContent>
            </Tooltip>
          )}
        </div>
      )}
    </div>
  )
}
