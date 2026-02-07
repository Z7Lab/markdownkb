import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Plus, RefreshCw, Trash2 } from "lucide-react"

interface FileActionsProps {
  status: string
  includeRag: boolean
  loading?: boolean
  onToggleRag: (checked: boolean) => void
  onIndexFile: () => void
  onReindexFile: () => void
  onUnindexFile: () => void
  variant?: "toggle-only" | "buttons-only" | "full"
  layout?: "row" | "column"
}

export function FileActions({
  status,
  includeRag,
  loading = false,
  onToggleRag,
  onIndexFile,
  onReindexFile,
  onUnindexFile,
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
    <div className={containerClass} onClick={(e) => e.stopPropagation()}>
      {/* Include RAG Toggle */}
      {showToggle && (
        <Tooltip>
          <TooltipTrigger asChild>
            <div className={layout === "column" ? "flex items-center justify-between p-3 border rounded-lg" : "flex items-center gap-2"}>
              <span className={layout === "column" ? "text-sm font-medium" : "text-xs font-medium"}>
                Include in RAG
              </span>
              <Switch
                checked={includeRag}
                disabled={loading || status === "not_indexed"}
                onCheckedChange={onToggleRag}
              />
            </div>
          </TooltipTrigger>
          <TooltipContent>
            {status === "not_indexed"
              ? "Index the file first to include in RAG"
              : includeRag
                ? "File is included in RAG search results"
                : "File is excluded from RAG search results"}
          </TooltipContent>
        </Tooltip>
      )}

      {/* Action Buttons */}
      {showButtons && (
        <div className={layout === "column" ? "flex gap-2" : "flex gap-1"}>
          {isNotIndexed && includeRag && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  disabled={loading}
                  onClick={onIndexFile}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Index this file</TooltipContent>
            </Tooltip>
          )}
          {isIndexed && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  disabled={loading}
                  onClick={onReindexFile}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Re-index this file</TooltipContent>
            </Tooltip>
          )}
          {(isIndexed || status === "error") && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive hover:text-destructive"
                  disabled={loading}
                  onClick={onUnindexFile}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Remove from index</TooltipContent>
            </Tooltip>
          )}
        </div>
      )}
    </div>
  )
}
