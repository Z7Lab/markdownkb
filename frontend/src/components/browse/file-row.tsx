import React from "react"
import { TableCell, TableRow } from "@/components/ui/table"
import { basename, dirname } from "@/lib/utils"
import { FileActions } from "./file-actions"
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
        <FileActions
          status={file.status}
          includeRag={file.include_rag === 1}
          loading={loading}
          onToggleRag={(checked) => onToggleRag(file.path, checked)}
          onIndexFile={() => onIndexFile(file.path)}
          onReindexFile={() => onReindexFile(file.path)}
          onUnindexFile={() => onUnindexFile(file.path)}
          variant="toggle-only"
        />
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
        <FileActions
          status={file.status}
          includeRag={file.include_rag === 1}
          loading={loading}
          onToggleRag={(checked) => onToggleRag(file.path, checked)}
          onIndexFile={() => onIndexFile(file.path)}
          onReindexFile={() => onReindexFile(file.path)}
          onUnindexFile={() => onUnindexFile(file.path)}
          variant="buttons-only"
        />
      </TableCell>
    </TableRow>
  )
})
