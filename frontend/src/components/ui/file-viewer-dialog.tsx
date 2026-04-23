import { useEffect, useRef, useState } from "react"
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
import { Pencil, Copy, ChevronLeft, ChevronRight, ChevronUp, ChevronDown, Search, X, BookOpen, History } from "lucide-react"
import { useTextSearch } from "@/hooks/use-text-search"
import { useFileViewer } from "@/hooks/use-file-viewer"
import { useWikiCompileAvailable } from "@/hooks/use-wiki-compile-available"
import { toast } from "sonner"
import { copyToClipboard, parseFrontmatter } from "@/lib/utils"
import { TagEditDialog } from "@/components/tags/tag-edit-dialog"
import { FileActions } from "@/components/browse/file-actions"
import { ConfirmDialog } from "./confirm-dialog"
import { WikiCompileDialog } from "@/components/wiki/wiki-compile-dialog"
import { HistoryDialog } from "@/components/versioning/history-dialog"

export function FileViewerDialog({
  path,
  onClose,
  bucketId,
}: {
  path: string | null
  onClose: () => void
  bucketId?: string | null
}) {
  const {
    rawContent, loading, actionLoading, fileStatus,
    editDialogOpen, setEditDialogOpen,
    pendingUnindex, setPendingUnindex,
    page, totalPages, totalLines, fileTags, copyingAll,
    fetchPage, handleSaveTags, handleToggleRag,
    handleIndexFile, handleReindexFile, handleUnindexFile, handleCopyContent,
  } = useFileViewer(path, bucketId)

  const {
    containerRef: searchContainerRef,
    isOpen: searchIsOpen,
    close: searchClose,
    open: searchOpen,
    query: searchQuery,
    setQuery: setSearchQuery,
    matchCount: searchMatchCount,
    currentMatch: searchCurrentMatch,
    nextMatch: searchNextMatch,
    prevMatch: searchPrevMatch,
  } = useTextSearch()
  const searchInputRef = useRef<HTMLInputElement>(null)
  const wikiCompileAvailable = useWikiCompileAvailable()
  const [compileDialogOpen, setCompileDialogOpen] = useState(false)
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false)

  // Focus search input when opened
  useEffect(() => {
    if (searchIsOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50)
    }
  }, [searchIsOpen])

  // Clear search when file changes
  useEffect(() => {
    searchClose()
  }, [path, searchClose])

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
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 gap-1.5"
                  onClick={() => setHistoryDialogOpen(true)}
                  disabled={loading}
                  title="View revision history for this file"
                >
                  <History className="h-3.5 w-3.5" />
                  History
                </Button>
                {wikiCompileAvailable && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1.5"
                    onClick={() => setCompileDialogOpen(true)}
                    disabled={loading}
                    title="Synthesize a summary page into a writable wiki source"
                  >
                    <BookOpen className="h-3.5 w-3.5" />
                    Compile
                  </Button>
                )}
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
          {searchIsOpen && (
            <div className="flex items-center gap-2 px-6 py-2 border-b bg-muted/30">
              <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <Input
                ref={searchInputRef}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault()
                    if (e.shiftKey) searchPrevMatch()
                    else searchNextMatch()
                  }
                  if (e.key === "Escape") searchClose()
                }}
                placeholder="Find in file..."
                className="h-7 text-xs flex-1"
              />
              {searchMatchCount > 0 && (
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  {searchCurrentMatch} of {searchMatchCount}
                </span>
              )}
              {searchQuery && searchMatchCount === 0 && (
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  No matches
                </span>
              )}
              <Button variant="ghost" size="icon" className="h-6 w-6" aria-label="Previous match" onClick={searchPrevMatch} disabled={searchMatchCount === 0}>
                <ChevronUp className="h-3.5 w-3.5" />
              </Button>
              <Button variant="ghost" size="icon" className="h-6 w-6" aria-label="Next match" onClick={searchNextMatch} disabled={searchMatchCount === 0}>
                <ChevronDown className="h-3.5 w-3.5" />
              </Button>
              <Button variant="ghost" size="icon" className="h-6 w-6" aria-label="Close search" onClick={searchClose}>
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}

          {/* Search toggle button (when search is closed) */}
          {!searchIsOpen && !loading && content && (
            <div className="flex justify-end px-6 py-1">
              <Button variant="ghost" size="sm" className="h-6 text-xs text-muted-foreground" onClick={searchOpen}>
                <Search className="h-3 w-3 mr-1" />
                Find
              </Button>
            </div>
          )}

          <ScrollArea className="flex-1 min-h-0 border rounded-md p-4">
            <div ref={searchContainerRef}>
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
                onClick={() => handleCopyContent(isMarkdown)}
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
          <WikiCompileDialog
            open={compileDialogOpen}
            sourcePath={path}
            onClose={() => setCompileDialogOpen(false)}
          />
          <HistoryDialog
            open={historyDialogOpen}
            path={path}
            onClose={() => setHistoryDialogOpen(false)}
            onRestored={() => path && fetchPage(path, 1)}
          />
        </>
      )}
    </>
  )
}
