import React from "react"
import { basename, dirname } from "@/lib/utils"
import { FileActions } from "./file-actions"
import type { TrackedFile } from "@/lib/types"

interface FileRowProps {
  file: TrackedFile
  busy: boolean
  gridTemplate: string
  onToggleRag: (path: string, checked: boolean) => void
  onIndexFile: (path: string) => void
  onReindexFile: (path: string) => void
  onUnindexFile: (path: string) => void
  onViewFile: (path: string) => void
}

export const FileRow = React.memo(function FileRow({
  file,
  busy,
  gridTemplate,
  onToggleRag,
  onIndexFile,
  onReindexFile,
  onUnindexFile,
  onViewFile,
}: FileRowProps) {
  return (
    <div
      className="grid items-center border-b hover:bg-muted/50 cursor-pointer transition-colors text-sm"
      style={{ gridTemplateColumns: gridTemplate }}
      onClick={() => onViewFile(file.path)}
    >
      <div className="px-2 py-2 font-mono truncate overflow-hidden">
        {basename(file.path)}
      </div>
      <div className="px-2 py-2 text-muted-foreground truncate overflow-hidden">
        {dirname(file.path)}
      </div>
      <div className="px-2 py-2 flex justify-center">
        <FileActions
          status={file.status}
          includeRag={file.include_rag === 1}
          busy={busy}
          onToggleRag={(checked) => onToggleRag(file.path, checked)}
          onIndexFile={() => onIndexFile(file.path)}
          onReindexFile={() => onReindexFile(file.path)}
          onUnindexFile={() => onUnindexFile(file.path)}
          variant="toggle-only"
        />
      </div>
      <div className="px-2 py-2">
        {file.status === "not_indexed" ? (
          <span className="text-muted-foreground">not indexed</span>
        ) : file.status === "indexing" ? (
          <span className="text-blue-500">indexing</span>
        ) : file.status === "error" ? (
          <span className="text-destructive">error</span>
        ) : (
          file.status
        )}
      </div>
      <div className="px-2 py-2 text-center">
        {file.chunk_count}
      </div>
      <div className="px-2 py-2">
        <FileActions
          status={file.status}
          includeRag={file.include_rag === 1}
          busy={busy}
          onToggleRag={(checked) => onToggleRag(file.path, checked)}
          onIndexFile={() => onIndexFile(file.path)}
          onReindexFile={() => onReindexFile(file.path)}
          onUnindexFile={() => onUnindexFile(file.path)}
          variant="buttons-only"
        />
      </div>
    </div>
  )
})
