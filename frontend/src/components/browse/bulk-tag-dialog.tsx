import { useState, useEffect, useMemo } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { Tag, X, Plus } from "lucide-react"
import type { TrackedFile } from "@/lib/types"

type Mode = "add" | "remove" | "replace"

export function BulkTagDialog({
  open,
  onOpenChange,
  selectedFiles,
  allFiles,
  onApply,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  selectedFiles: Set<string>
  allFiles: TrackedFile[]
  onApply: (paths: string[], tags: string[], mode: Mode) => void
}) {
  const [mode, setMode] = useState<Mode>("add")
  const [tags, setTags] = useState<string[]>([])
  const [input, setInput] = useState("")

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setMode("add")
      setTags([])
      setInput("")
    }
  }, [open])

  // Collect all existing tags for suggestions
  const existingTags = useMemo(() => {
    const tagSet = new Set<string>()
    for (const f of allFiles) {
      if (f.tags) {
        for (const t of f.tags.split(",")) {
          const trimmed = t.trim()
          if (trimmed) tagSet.add(trimmed)
        }
      }
    }
    return Array.from(tagSet).sort()
  }, [allFiles])

  // Tags on the selected files specifically
  const selectedFileTags = useMemo(() => {
    const tagSet = new Set<string>()
    for (const f of allFiles) {
      if (selectedFiles.has(f.path) && f.tags) {
        for (const t of f.tags.split(",")) {
          const trimmed = t.trim()
          if (trimmed) tagSet.add(trimmed)
        }
      }
    }
    return Array.from(tagSet).sort()
  }, [allFiles, selectedFiles])

  const suggestions = existingTags.filter(
    (t) => !tags.includes(t) && (!input || t.toLowerCase().includes(input.toLowerCase()))
  )

  function addTag(tag: string) {
    const trimmed = tag.trim()
    if (trimmed && !tags.includes(trimmed)) {
      setTags([...tags, trimmed])
    }
    setInput("")
  }

  function removeTag(tag: string) {
    setTags(tags.filter((t) => t !== tag))
  }

  const paths = Array.from(selectedFiles)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Bulk Tag — {paths.length} files</DialogTitle>
          <DialogDescription>
            Add, remove, or replace tags on selected files.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Mode selector */}
          <div className="space-y-1.5">
            <Label>Action</Label>
            <div className="flex gap-2">
              {(["add", "remove", "replace"] as Mode[]).map((m) => (
                <Button
                  key={m}
                  variant={mode === m ? "default" : "outline"}
                  size="sm"
                  onClick={() => setMode(m)}
                >
                  {m === "add" ? "Add tags" : m === "remove" ? "Remove tags" : "Replace all"}
                </Button>
              ))}
            </div>
          </div>

          {/* Tag input */}
          <div className="space-y-1.5">
            <Label>Tags</Label>
            <div className="flex flex-wrap gap-1 mb-2 min-h-[28px]">
              {tags.map((t) => (
                <Badge key={t} variant="secondary" className="gap-1 cursor-pointer" onClick={() => removeTag(t)}>
                  <Tag className="h-2.5 w-2.5" />
                  {t}
                  <X className="h-2.5 w-2.5" />
                </Badge>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a tag name..."
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault()
                    addTag(input)
                  }
                }}
              />
              <Button
                variant="outline"
                size="icon"
                onClick={() => addTag(input)}
                disabled={!input.trim()}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Suggestions */}
          {suggestions.length > 0 && (
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">
                {mode === "remove" ? "Tags on selected files" : "Existing tags"}
              </Label>
              <div className="flex flex-wrap gap-1">
                {(mode === "remove" ? selectedFileTags.filter((t) => !tags.includes(t)) : suggestions)
                  .slice(0, 20)
                  .map((t) => (
                    <Badge
                      key={t}
                      variant="outline"
                      className="cursor-pointer hover:bg-accent"
                      onClick={() => addTag(t)}
                    >
                      <Plus className="h-2 w-2 mr-0.5" />
                      {t}
                    </Badge>
                  ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              onApply(paths, tags, mode)
              onOpenChange(false)
            }}
            disabled={tags.length === 0}
          >
            {mode === "add" ? "Add" : mode === "remove" ? "Remove" : "Replace"} tags on {paths.length} files
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
