import React, { useState } from "react"
import { basename, dirname } from "@/lib/utils"
import { FileActions } from "./file-actions"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Tag, Plus, X } from "lucide-react"
import type { TrackedFile } from "@/lib/types"

interface FileRowProps {
  file: TrackedFile
  busy: boolean
  gridTemplate: string
  selected?: boolean
  onToggleSelect?: (path: string) => void
  onToggleRag: (path: string, checked: boolean) => void
  onIndexFile: (path: string) => void
  onReindexFile: (path: string) => void
  onUnindexFile: (path: string) => void
  onViewFile: (path: string) => void
  onUpdateTags: (path: string, tags: string[]) => void
}

function parseTags(raw: string): string[] {
  if (!raw) return []
  return raw.split(",").map((t) => t.trim()).filter(Boolean)
}

export const FileRow = React.memo(function FileRow({
  file,
  busy,
  gridTemplate,
  selected,
  onToggleSelect,
  onToggleRag,
  onIndexFile,
  onReindexFile,
  onUnindexFile,
  onViewFile,
  onUpdateTags,
}: FileRowProps) {
  const [editingTags, setEditingTags] = useState(false)
  const [newTag, setNewTag] = useState("")
  const tags = parseTags(file.tags)

  function addTag() {
    const tag = newTag.trim()
    if (tag && !tags.includes(tag)) {
      onUpdateTags(file.path, [...tags, tag])
    }
    setNewTag("")
  }

  function removeTag(tag: string) {
    onUpdateTags(file.path, tags.filter((t) => t !== tag))
  }

  return (
    <div
      className={`grid items-center border-b hover:bg-muted/50 cursor-pointer transition-colors text-sm ${selected ? "bg-primary/5" : ""}`}
      style={{ gridTemplateColumns: gridTemplate }}
      onClick={() => onViewFile(file.path)}
    >
      <div className="px-2 py-2 flex items-center gap-2 font-mono truncate overflow-hidden">
        {onToggleSelect && (
          <Checkbox
            checked={selected}
            onCheckedChange={() => onToggleSelect(file.path)}
            onClick={(e) => e.stopPropagation()}
            className="shrink-0"
          />
        )}
        <span className="truncate">{basename(file.path)}</span>
      </div>
      <div className="px-2 py-2 text-muted-foreground truncate overflow-hidden">
        {dirname(file.path)}
      </div>
      <div
        className="px-2 py-1.5 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {editingTags ? (
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap gap-0.5">
              {tags.map((t) => (
                <Badge
                  key={t}
                  variant="outline"
                  className="text-[10px] gap-0.5 cursor-pointer hover:bg-destructive/10"
                  onClick={() => removeTag(t)}
                >
                  {t}
                  <X className="h-2 w-2" />
                </Badge>
              ))}
            </div>
            <div className="flex gap-1">
              <Input
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                placeholder="Add tag..."
                className="h-6 text-[10px] px-1.5"
                onKeyDown={(e) => {
                  if (e.key === "Enter") { e.preventDefault(); addTag() }
                  if (e.key === "Escape") setEditingTags(false)
                }}
                autoFocus
              />
              <button
                className="text-muted-foreground hover:text-foreground shrink-0"
                onClick={() => setEditingTags(false)}
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          </div>
        ) : (
          <div
            className="flex flex-wrap gap-0.5 cursor-pointer group min-h-[20px]"
            onClick={() => setEditingTags(true)}
          >
            {tags.length > 0 ? (
              tags.map((t) => (
                <Badge key={t} variant="outline" className="text-[10px] font-normal gap-0.5">
                  <Tag className="h-2 w-2" />
                  {t}
                </Badge>
              ))
            ) : (
              <span className="text-[10px] text-muted-foreground opacity-0 group-hover:opacity-100 flex items-center gap-0.5">
                <Plus className="h-2.5 w-2.5" />
                add tags
              </span>
            )}
          </div>
        )}
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
        ) : file.status === "missing" ? (
          <span className="text-destructive/70">missing</span>
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
