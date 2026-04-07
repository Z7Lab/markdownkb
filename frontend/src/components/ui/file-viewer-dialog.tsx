import { useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Input } from "@/components/ui/input"
import { Markdown } from "@/components/ui/markdown"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Pencil, Copy, ChevronLeft, ChevronRight, ChevronUp, ChevronDown, Search, X } from "lucide-react"
import { useTextSearch } from "@/hooks/use-text-search"
import { toast } from "sonner"
import { copyToClipboard } from "@/lib/utils"
import { TagEditDialog } from "@/components/tags/tag-edit-dialog"
import { FileActions } from "@/components/browse/file-actions"
import { ConfirmDialog } from "./confirm-dialog"

interface ParsedContent {
  tags: string[]
  content: string
}

interface FileReadResponse {
  content: string
  page?: number
  total_pages?: number
  total_lines?: number
  page_size?: number
}

const PAGE_SIZE = 5000

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

// TODO: Extract data fetching and state management into a useFileViewer hook.
// Move parseFrontmatter to a shared utility (used by both this dialog and other components).
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
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalLines, setTotalLines] = useState(0)
  const [fileTags, setFileTags] = useState<string[]>([])
  const [copyingAll, setCopyingAll] = useState(false)

  const fetchPage = async (filePath: string, pageNum: number, signal?: AbortSignal) => {
    setLoading(true)
    try {
      const res = await api.get<FileReadResponse>(
        `/api/file?path=${encodeURIComponent(filePath)}&page=${pageNum}&page_size=${PAGE_SIZE}`,
        signal,
      )
      if (signal?.aborted) return
      setRawContent(res.content)
      setPage(res.page ?? pageNum)
      setTotalPages(res.total_pages ?? 1)
      setTotalLines(res.total_lines ?? 0)
      // Parse and persist tags from page 1 (frontmatter only appears on first page)
      if (pageNum === 1 && filePath.endsWith(".md")) {
        const { tags } = parseFrontmatter(res.content)
        setFileTags(tags)
      }
    } catch {
      if (signal?.aborted) return
      setRawContent("Error loading file.")
      setTotalPages(1)
      setTotalLines(0)
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }

  useEffect(() => {
    if (!path) return
    setRawContent("")
    setPage(1)
    setTotalPages(1)
    setTotalLines(0)
    setFileTags([])

    const controller = new AbortController()

    // Load file content (page 1)
    fetchPage(path, 1, controller.signal)

    // Check file status (using lightweight endpoint)
    api
      .get<{ path: string; status: string; include_rag: number; chunk_count: number }>(
        `/api/file/status?path=${encodeURIComponent(path)}`,
        controller.signal,
      )
      .then((res) => {
        if (controller.signal.aborted) return
        setFileStatus({
          status: res.status,
          include_rag: res.include_rag,
          chunk_count: res.chunk_count,
        })
      })
      .catch(() => {
        if (controller.signal.aborted) return
        setFileStatus({
          status: "not_indexed",
          include_rag: 1,
          chunk_count: 0,
        })
      })

    return () => controller.abort()
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

      // Reload content to reflect changes (page 1 since tags may shift content)
      // fetchPage will also update fileTags from the new page 1 content
      await fetchPage(path, 1)

      toast.success(createBackup ? "Tags updated! Backup created." : "Tags updated successfully!")

      if (shouldReindex) {
        try {
          await api.post("/api/files/reindex", { path })
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
      await api.put("/api/files/toggle-rag", { path, include: checked })
      setFileStatus((prev) => ({ ...prev, include_rag: checked ? 1 : 0 }))
      toast.success(checked ? "File included in RAG" : "File excluded from RAG")
    })
  }

  const handleIndexFile = () => withAction(async () => {
    await api.post("/api/files/index", { path })
    toast.success("File indexed successfully!")
  })

  const handleReindexFile = () => withAction(async () => {
    await api.post("/api/files/reindex", { path })
    toast.success("File reindexed successfully!")
  })

  const handleUnindexFile = async () => {
    setPendingUnindex(false)
    await withAction(async () => {
      await api.post("/api/files/unindex", { path })
      toast.success("File removed from index")
    })
  }

  const textSearch = useTextSearch()
  const searchInputRef = useRef<HTMLInputElement>(null)

  // Focus search input when opened
  useEffect(() => {
    if (textSearch.isOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50)
    }
  }, [textSearch.isOpen])

  // Clear search when file changes
  useEffect(() => {
    textSearch.close()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path])

  const filename = path?.split("/").pop() ?? ""
  const isMarkdown = filename.endsWith(".md")
  // Only strip frontmatter on page 1 of markdown files; otherwise show raw content
  const { content } = (page === 1 && isMarkdown) ? parseFrontmatter(rawContent) : { content: rawContent }
  const tags = fileTags

  const handleCopyPath = async () => {
    if (!path) return
    const ok = await copyToClipboard(path)
    if (ok) {
      toast.success("File path copied to clipboard")
    } else {
      toast.error("Failed to copy — clipboard access denied")
    }
  }

  const handleCopyContent = async () => {
    if (!path) return
    setCopyingAll(true)
    try {
      // Fetch full file content (no pagination) for copying
      const res = await api.get<FileReadResponse>(
        `/api/file?path=${encodeURIComponent(path)}`
      )
      const fullContent = isMarkdown ? parseFrontmatter(res.content).content : res.content
      const ok = await copyToClipboard(fullContent)
      if (ok) {
        toast.success("File content copied to clipboard")
      } else {
        toast.error("Failed to copy — clipboard access denied")
      }
    } catch {
      toast.error("Failed to load file content for copying")
    } finally {
      setCopyingAll(false)
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
          {/* Find in file bar */}
          {textSearch.isOpen && (
            <div className="flex items-center gap-2 px-6 py-2 border-b bg-muted/30">
              <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <Input
                ref={searchInputRef}
                value={textSearch.query}
                onChange={(e) => textSearch.setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault()
                    if (e.shiftKey) textSearch.prevMatch()
                    else textSearch.nextMatch()
                  }
                  if (e.key === "Escape") textSearch.close()
                }}
                placeholder="Find in file..."
                className="h-7 text-xs flex-1"
              />
              {textSearch.matchCount > 0 && (
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  {textSearch.currentMatch} of {textSearch.matchCount}
                </span>
              )}
              {textSearch.query && textSearch.matchCount === 0 && (
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  No matches
                </span>
              )}
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={textSearch.prevMatch} disabled={textSearch.matchCount === 0}>
                <ChevronUp className="h-3.5 w-3.5" />
              </Button>
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={textSearch.nextMatch} disabled={textSearch.matchCount === 0}>
                <ChevronDown className="h-3.5 w-3.5" />
              </Button>
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={textSearch.close}>
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}

          {/* Search toggle button (when search is closed) */}
          {!textSearch.isOpen && !loading && content && (
            <div className="flex justify-end px-6 py-1">
              <Button variant="ghost" size="sm" className="h-6 text-xs text-muted-foreground" onClick={textSearch.open}>
                <Search className="h-3 w-3 mr-1" />
                Find
              </Button>
            </div>
          )}

          <ScrollArea className="flex-1 min-h-0 border rounded-md p-4">
            <div ref={textSearch.containerRef}>
              {loading ? (
                <p className="text-sm text-muted-foreground animate-pulse">
                  Loading...
                </p>
              ) : (
                <Markdown>{content}</Markdown>
              )}
            </div>
          </ScrollArea>
          <AlertDialogFooter className="flex items-center justify-between sm:justify-between">
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopyContent}
                disabled={loading || copyingAll || !content}
              >
                <Copy className="h-3.5 w-3.5 mr-1.5" />
                {copyingAll ? "Copying..." : "Copy Content"}
              </Button>
            </div>
            {totalPages > 1 && (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8"
                  disabled={loading || page <= 1}
                  onClick={() => path && fetchPage(path, page - 1)}
                  aria-label="Previous page"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm text-muted-foreground whitespace-nowrap">
                  Page {page} of {totalPages} ({totalLines.toLocaleString()} lines)
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8"
                  disabled={loading || page >= totalPages}
                  onClick={() => path && fetchPage(path, page + 1)}
                  aria-label="Next page"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
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
