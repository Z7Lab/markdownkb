import React from "react"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { TableCell, TableRow } from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Plus, RefreshCw, Trash2 } from "lucide-react"
import { basename, dirname } from "@/lib/utils"
import type { TrackedFile } from "@/lib/types"

interface FileRowProps {
  file: TrackedFile
  loading: boolean
  onToggleRag: (path: string, checked: boolean) => void
  onIndexFile: (path: string) => void
  onReindexFile: (path: string) => void
  onUnindexFile: (path: string) => void
  onViewFile: (path: string) => void
}

export const FileRow = React.memo(function FileRow({
  file,
  loading,
  onToggleRag,
  onIndexFile,
  onReindexFile,
  onUnindexFile,
  onViewFile,
}: FileRowProps) {
  const isIndexed = file.status === "complete"
  const isNotIndexed = file.status === "not_indexed" || file.status === "pending"
  const ragOn = file.include_rag === 1

  return (
    <TableRow
      className="cursor-pointer"
      onClick={() => onViewFile(file.path)}
    >
      <TableCell className="font-mono text-sm truncate max-w-[200px]">
        {basename(file.path)}
      </TableCell>
      <TableCell className="text-sm text-muted-foreground truncate max-w-[180px]">
        {dirname(file.path)}
      </TableCell>
      <TableCell>
        <div className="flex justify-center">
          <Switch
            checked={ragOn}
            disabled={loading || file.status === "not_indexed"}
            onClick={(e) => e.stopPropagation()}
            onCheckedChange={(checked) => onToggleRag(file.path, checked)}
          />
        </div>
      </TableCell>
      <TableCell className="text-sm">
        {file.status === "not_indexed" ? (
          <span className="text-muted-foreground">not indexed</span>
        ) : file.status === "indexing" ? (
          <span className="text-blue-500">indexing</span>
        ) : file.status === "error" ? (
          <span className="text-destructive">error</span>
        ) : (
          file.status
        )}
      </TableCell>
      <TableCell>
        <div className="flex justify-center">{file.chunk_count}</div>
      </TableCell>
      <TableCell>
        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
          {isNotIndexed && ragOn && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  disabled={loading}
                  onClick={() => onIndexFile(file.path)}
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
                  onClick={() => onReindexFile(file.path)}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Re-index this file</TooltipContent>
            </Tooltip>
          )}
          {(isIndexed || file.status === "error") && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive hover:text-destructive"
                  disabled={loading}
                  onClick={() => onUnindexFile(file.path)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Remove from index</TooltipContent>
            </Tooltip>
          )}
        </div>
      </TableCell>
    </TableRow>
  )
})
