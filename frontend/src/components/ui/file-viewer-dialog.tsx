import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Markdown } from "@/components/ui/markdown"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Pencil, Copy } from "lucide-react"
import { toast } from "sonner"
import { TagEditDialog } from "./tag-edit-dialog"
import { FileActions } from "@/components/browse/file-actions"
import { ConfirmDialog } from "./confirm-dialog"

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
  const [actionLoading, setActionLoading] = useState(false)
  const [fileStatus, setFileStatus] = useState({
    status: "not_indexed",
    include_rag: 1,
    chunk_count: 0,
  })
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [pendingUnindex, setPendingUnindex] = useState(false)

  useEffect(() => {
    if (!path) return
    setLoading(true)
    setRawContent("")

    // Load file content
    api
      .get<{ content: string }>(`/api/file?path=${encodeURIComponent(path)}`)
      .then((res) => setRawContent(res.content))
      .catch(() => setRawContent("Error loading file."))
      .finally(() => setLoading(false))

    // Check file status (using lightweight endpoint)
    api
      .get<{ path: string; status: string; include_rag: number; chunk_count: number }>(
        `/api/file/status?path=${encodeURIComponent(path)}`
      )
      .then((res) => {
        setFileStatus({
          status: res.status,
          include_rag: res.include_rag,
          chunk_count: res.chunk_count,
        })
      })
      .catch(() => {
        setFileStatus({
          status: "not_indexed",
          include_rag: 1,
          chunk_count: 0,
        })
      })
  }, [path])

  /** Refresh file status from the lightweight status endpoint */
  const refreshFileStatus = async () => {
    if (!path) return
    const statusRes = await api.get<{ status: string; include_rag: number; chunk_count: number }>(
      `/api/file/status?path=${encodeURIComponent(path)}`
    )
    setFileStatus({
      status: statusRes.status,
      include_rag: statusRes.include_rag,
      chunk_count: statusRes.chunk_count,
    })
  }

  /** Run a file action with loading state and status refresh */
  const withAction = async (fn: () => Promise<void>) => {
    if (!path) return
    setActionLoading(true)
    try {
      await fn()
      await refreshFileStatus()
    } finally {
      setActionLoading(false)
    }
  }

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

      toast.success(createBackup ? "Tags updated! Backup created." : "Tags updated successfully!")

      if (shouldReindex) {
        try {
          await api.post("/api/files/reindex", { paths: [path] })
          toast.success("File reindexed successfully!")
          await refreshFileStatus()
        } catch (err) {
          toast.error(`Failed to reindex: ${(err as Error).message}`)
        }
      }
    } catch (err) {
      toast.error(`Failed to update tags: ${(err as Error).message}`)
      throw err
    }
  }

  const handleToggleRag = async (checked: boolean) => {
    await withAction(async () => {
      await api.post("/api/files/toggle-rag", { path, include_rag: checked })
      setFileStatus((prev) => ({ ...prev, include_rag: checked ? 1 : 0 }))
      toast.success(checked ? "File included in RAG" : "File excluded from RAG")
    })
  }

  const handleIndexFile = () => withAction(async () => {
    await api.post("/api/files/index", { paths: [path] })
    toast.success("File indexed successfully!")
  })

  const handleReindexFile = () => withAction(async () => {
    await api.post("/api/files/reindex", { paths: [path] })
    toast.success("File reindexed successfully!")
  })

  const handleUnindexFile = async () => {
    setPendingUnindex(false)
    await withAction(async () => {
      await api.post("/api/files/unindex", { paths: [path] })
      toast.success("File removed from index")
    })
  }

  const { tags, content} = parseFrontmatter(rawContent)
  const filename = path?.split("/").pop() ?? ""
  const isMarkdown = filename.endsWith(".md")

  const handleCopyPath = async () => {
    if (!path) return
    try {
      await navigator.clipboard.writeText(path)
      toast.success("File path copied to clipboard")
    } catch {
      toast.error("Failed to copy — clipboard access denied")
    }
  }

  return (
    <>
      <AlertDialog open={!!path} onOpenChange={(open) => { if (!open) onClose() }}>
        <AlertDialogContent className="!max-w-6xl !h-[85vh] flex flex-col">
          {/* Custom header with proper flex layout */}
          <div className="flex items-start justify-between gap-4 px-6 pt-6">
            <div className="flex-1 min-w-0">
              <AlertDialogTitle className="font-mono text-sm truncate">
                {filename}
              </AlertDialogTitle>
              <div className="flex items-center gap-1 mt-1">
                <p className="text-xs text-muted-foreground truncate">{path}</p>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5 shrink-0"
                  onClick={handleCopyPath}
                  aria-label="Copy file path"
                >
                  <Copy className="h-3 w-3" />
                </Button>
              </div>
            </div>
            {isMarkdown && (
              <div className="flex items-center gap-2 shrink-0">
                <FileActions
                  status={fileStatus.status}
                  includeRag={fileStatus.include_rag === 1}
                  busy={actionLoading}
                  onToggleRag={handleToggleRag}
                  onIndexFile={handleIndexFile}
                  onReindexFile={handleReindexFile}
                  onUnindexFile={() => setPendingUnindex(true)}
                  variant="full"
                  layout="row"
                />
              </div>
            )}
          </div>

          {/* Tags section */}
          {isMarkdown && (
            <div className="flex items-center gap-2 pt-3 pb-2 min-h-[28px] border-b px-6">
              <div className="flex flex-wrap gap-1.5">
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
        <>
          <TagEditDialog
            open={editDialogOpen}
            onOpenChange={setEditDialogOpen}
            currentTags={tags}
            filePath={path}
            isIndexed={fileStatus.status === "complete"}
            onSave={handleSaveTags}
          />
          <ConfirmDialog
            open={pendingUnindex}
            onOpenChange={setPendingUnindex}
            title="Remove from index?"
            description={`This will delete all chunks for "${path.split("/").pop()}" from the vector store and exclude it from RAG.`}
            confirmLabel="Unindex"
            variant="destructive"
            onConfirm={handleUnindexFile}
          />
        </>
      )}
    </>
  )
}
