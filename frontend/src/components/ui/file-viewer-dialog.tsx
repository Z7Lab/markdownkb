import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Markdown } from "@/components/ui/markdown"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Pencil } from "lucide-react"
import { toast } from "sonner"
import { TagEditDialog } from "./tag-edit-dialog"

interface ParsedContent {
  tags: string[]
  content: string
}

function parseFrontmatter(raw: string): ParsedContent {
  const frontmatterRegex = /^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/
  const match = raw.match(frontmatterRegex)

  if (!match) {
    return { tags: [], content: raw }
  }

  const [, frontmatter, content] = match

  // Try inline array format: tags: [tag1, tag2]
  const inlineMatch = frontmatter.match(/tags:\s*\[(.*?)\]/)
  if (inlineMatch) {
    const tags = inlineMatch[1]
      .split(',')
      .map(t => t.trim().replace(/['"]/g, ''))
      .filter(Boolean)
    return { tags, content }
  }

  // Try YAML list format:
  // tags:
  // - tag1
  // - tag2
  const listMatch = frontmatter.match(/tags:\s*\n((?:\s*-\s*.+\n?)+)/)
  if (listMatch) {
    const tags = listMatch[1]
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.startsWith('-'))
      .map(line => line.substring(1).trim().replace(/['"]/g, ''))
      .filter(Boolean)
    return { tags, content }
  }

  return { tags: [], content }
}

export function FileViewerDialog({
  path,
  onClose,
}: {
  path: string | null
  onClose: () => void
}) {
  const [rawContent, setRawContent] = useState("")
  const [loading, setLoading] = useState(false)
  const [isIndexed, setIsIndexed] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)

  useEffect(() => {
    if (!path) return
    // Wrap state updates in Promise.resolve().then() to avoid set-state-in-effect warning
    Promise.resolve().then(() => {
      setLoading(true)
      setRawContent("")
    })

    // Load file content
    api
      .get<{ content: string }>(`/api/file?path=${encodeURIComponent(path)}`)
      .then((res) => setRawContent(res.content))
      .catch(() => setRawContent("Error loading file."))
      .finally(() => setLoading(false))

    // Check if file is indexed (using lightweight endpoint instead of fetching all files)
    api
      .get<{ path: string; status: string }>(`/api/file/status?path=${encodeURIComponent(path)}`)
      .then((res) => {
        setIsIndexed(res.status === "complete")
      })
      .catch(() => setIsIndexed(false))
  }, [path])

  const handleSaveTags = async (newTags: string[], createBackup: boolean, shouldReindex: boolean) => {
    if (!path) return

    try {
      await api.post("/api/tags/apply", {
        file_path: path,
        tags: newTags,
        merge_with_existing: false,
        create_backup: createBackup,
      })

      // Reload content to reflect changes
      const updated = await api.get<{ content: string }>(
        `/api/file?path=${encodeURIComponent(path)}`
      )
      setRawContent(updated.content)

      if (createBackup) {
        toast.success("Tags updated! Backup created.")
      } else {
        toast.success("Tags updated successfully!")
      }

      // Reindex if requested
      if (shouldReindex) {
        try {
          await api.post("/api/files/reindex", { paths: [path] })
          toast.success("File reindexed successfully!")
        } catch (err) {
          toast.error(`Failed to reindex: ${(err as Error).message}`)
        }
      }
    } catch (err) {
      toast.error(`Failed to update tags: ${(err as Error).message}`)
      throw err
    }
  }

  const { tags, content} = parseFrontmatter(rawContent)
  const filename = path?.split("/").pop() ?? ""
  const isMarkdown = filename.endsWith(".md")

  return (
    <>
      <AlertDialog open={!!path} onOpenChange={(open) => { if (!open) onClose() }}>
        <AlertDialogContent className="!max-w-6xl !h-[85vh] flex flex-col">
          <AlertDialogHeader>
            <div className="flex-1 min-w-0">
              <AlertDialogTitle className="font-mono text-sm truncate">
                {filename}
              </AlertDialogTitle>
              <p className="text-xs text-muted-foreground truncate">{path}</p>
            </div>
            {isMarkdown && (
              <div className="flex items-center gap-2 pt-2 min-h-[28px]">
                <div className="flex flex-wrap gap-1.5 flex-1">
                  {tags.length > 0 ? (
                    tags.map((tag) => (
                      <Badge key={tag} variant="secondary" className="text-xs">
                        {tag}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-xs text-muted-foreground italic">
                      No tags yet
                    </span>
                  )}
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 px-2 shrink-0"
                  onClick={() => setEditDialogOpen(true)}
                  disabled={loading}
                >
                  <Pencil className="h-3 w-3 mr-1" />
                  Edit
                </Button>
              </div>
            )}
          </AlertDialogHeader>
          <ScrollArea className="flex-1 min-h-0 border rounded-md p-4">
            {loading ? (
              <p className="text-sm text-muted-foreground animate-pulse">
                Loading...
              </p>
            ) : (
              <Markdown>{content}</Markdown>
            )}
          </ScrollArea>
          <AlertDialogFooter>
            <AlertDialogCancel>Close</AlertDialogCancel>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {path && (
          <TagEditDialog
          open={editDialogOpen}
          onOpenChange={setEditDialogOpen}
          currentTags={tags}
          filePath={path}
          isIndexed={isIndexed}
          onSave={handleSaveTags}
        />
      )}
    </>
  )
}
