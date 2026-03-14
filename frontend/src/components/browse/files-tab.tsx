import { useCallback, useEffect, useRef, useState } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { useFiles } from "@/hooks/use-files"
import { useTableSort } from "@/hooks/use-table-sort"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { useIndexEvents } from "@/hooks/use-index-events"
import { FolderTree } from "./folder-tree"
import { FileRow } from "./file-row"
import { BulkTagDialog } from "@/components/tags/bulk-tag-dialog"
import { AutoTagDialog } from "@/components/tags/auto-tag-dialog"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable"
import { ArrowDown, ArrowUp, FileDown, FileText, FileX, Loader2, RefreshCw, Search, Tag, Wand2, X } from "lucide-react"
import type { TrackedFile } from "@/lib/types"
import { basename, dirname, cn } from "@/lib/utils"

/** Multi-term AND: split on spaces, each term must substring-match in the path */
function filterMatch(text: string, pattern: string): boolean {
  const textLower = text.toLowerCase()
  const terms = pattern.toLowerCase().split(/\s+/).filter(Boolean)
  return terms.every((term) => textLower.includes(term))
}

const getValue = (f: TrackedFile, key: string): string | number | null => {
  switch (key) {
    case "file":
      return basename(f.path)
    case "folder":
      return dirname(f.path)
    case "tags":
      return f.tags || ""
    case "rag":
      return f.include_rag
    case "status":
      return f.status
    case "chunks":
      return f.chunk_count
    case "indexed":
      return f.indexed_at || ""
    default:
      return null
  }
}

// Column IDs and default sizes as percentages (must sum to 100)
const COL_IDS = ["file", "folder", "tags", "rag", "status", "chunks", "indexed", "actions"] as const
const DEFAULT_LAYOUT: Record<string, number> = {
  file: 20, folder: 20, tags: 12, rag: 8, status: 8, chunks: 6, indexed: 12, actions: 14,
}

function SortHeader({
  sortKey,
  activeSortKey,
  sortDir,
  onSort,
  children,
  className,
}: {
  sortKey: string
  activeSortKey: string | null
  sortDir: "asc" | "desc"
  onSort: (key: string) => void
  children: React.ReactNode
  className?: string
}) {
  const active = activeSortKey === sortKey
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      className={cn(
        "flex items-center gap-1 px-2 h-full text-sm font-medium text-foreground cursor-pointer select-none whitespace-nowrap overflow-hidden",
        className,
      )}
      aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : undefined}
    >
      {children}
      {active &&
        (sortDir === "asc" ? (
          <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
        ) : (
          <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
        ))}
    </button>
  )
}

/** Hook for debounced content search */
function useContentSearch(filterText: string, searchMode: "path" | "content") {
  const [contentMatches, setContentMatches] = useState<Set<string> | null>(null)
  const [contentSearching, setContentSearching] = useState(false)
  const contentDebounce = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (searchMode !== "content" || !filterText.trim()) {
      setContentMatches(null)
      return
    }
    if (contentDebounce.current) clearTimeout(contentDebounce.current)
    setContentSearching(true)
    contentDebounce.current = setTimeout(async () => {
      try {
        const res = await api.post<{ paths: string[] }>("/api/files/search", {
          query: filterText,
          top_k: 50,
        })
        setContentMatches(new Set(res.paths))
      } catch (err) {
        console.warn("Content search failed:", (err as Error).message)
        setContentMatches(new Set<string>())
      } finally {
        setContentSearching(false)
      }
    }, 400)
    return () => { if (contentDebounce.current) clearTimeout(contentDebounce.current) }
  }, [filterText, searchMode])

  const clearMatches = useCallback(() => setContentMatches(null), [])

  return { contentMatches, contentSearching, clearMatches }
}

/** Virtualized file list — only renders visible rows for large file sets */
function VirtualizedFileList({
  files,
  allFilesEmpty,
  busyPaths,
  gridTemplate,
  selected,
  onToggleSelect,
  onToggleRag,
  onIndexFile,
  onReindexFile,
  onUnindexFile,
  onViewFile,
  onUpdateTags,
}: {
  files: TrackedFile[]
  allFilesEmpty: boolean
  busyPaths: Set<string>
  gridTemplate: string
  selected: Set<string>
  onToggleSelect: (path: string) => void
  onToggleRag: (path: string, checked: boolean) => void
  onIndexFile: (path: string) => void
  onReindexFile: (path: string) => void
  onUnindexFile: (path: string) => void
  onViewFile: (path: string) => void
  onUpdateTags: (path: string, tags: string[]) => Promise<void>
}) {
  const parentRef = useRef<HTMLDivElement>(null)

  // eslint-disable-next-line react-hooks/incompatible-library -- isolated component, no memoization needed
  const virtualizer = useVirtualizer({
    count: files.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40,
    overscan: 10,
  })

  if (files.length === 0) {
    return (
      <div className="flex-1 overflow-auto min-h-0">
        <div className="text-center text-muted-foreground py-8">
          {allFilesEmpty ? "No markdown files found in watch directories." : "No files match your filter."}
        </div>
      </div>
    )
  }

  return (
    <div ref={parentRef} className="flex-1 overflow-auto min-h-0">
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: "relative" }}>
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const f = files[virtualRow.index]
          return (
            <div
              key={f.path}
              data-index={virtualRow.index}
              ref={virtualizer.measureElement}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <FileRow
                file={f}
                busy={busyPaths.has(f.path)}
                gridTemplate={gridTemplate}
                selected={selected.has(f.path)}
                onToggleSelect={onToggleSelect}
                onToggleRag={onToggleRag}
                onIndexFile={onIndexFile}
                onReindexFile={onReindexFile}
                onUnindexFile={onUnindexFile}
                onViewFile={onViewFile}
                onUpdateTags={onUpdateTags}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function FilesTab() {
  const { files, busyPaths, refresh, toggleRag, unindexFile, indexFile, reindexFile, indexAll, unindexSource, updateTags, bulkUpdateTags } = useFiles()
  const { isIndexing, lastIndexedAt } = useIndexEvents()
  const [filterText, setFilterText] = useState("")
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    await refresh()
    setRefreshing(false)
  }, [refresh])

  // Auto-refresh file list when indexing events arrive
  useEffect(() => {
    if (lastIndexedAt) refresh(true)
  }, [lastIndexedAt, refresh])
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null)
  const [viewingPath, setViewingPath] = useState<string | null>(null)
  const [pendingUnindex, setPendingUnindex] = useState<string | null>(null)
  const [confirmUnindexAll, setConfirmUnindexAll] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkTagOpen, setBulkTagOpen] = useState(false)
  const [autoTagOpen, setAutoTagOpen] = useState(false)
  const [sources, setSources] = useState<string[]>([])
  const [searchMode, setSearchMode] = useState<"path" | "content">("path")
  const { contentMatches, contentSearching, clearMatches } = useContentSearch(filterText, searchMode)
  const { sorted, sortKey, sortDir, onSort } = useTableSort(files, getValue)

  // Column sizes as percentages (synced from ResizablePanelGroup)
  const [colLayout, setColLayout] = useState(DEFAULT_LAYOUT)
  const handleLayoutChange = useCallback((layout: Record<string, number>) => {
    setColLayout(layout)
  }, [])
  const gridTemplate = COL_IDS.map((id) => `${colLayout[id] ?? 16}%`).join(" ")

  // Fetch sources for auto-tag dialog
  useEffect(() => {
    api.get<{ sources: string[] }>("/api/sources").then((res) => setSources(res.sources)).catch(() => { /* sources list for auto-tag is non-critical */ })
  }, [])

  const toggleSelect = useCallback((path: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }, [])

  const folderFiltered = selectedFolder
    ? sorted.filter((f) => {
        const dir = dirname(f.path)
        return dir === selectedFolder || dir.startsWith(selectedFolder + "/")
      })
    : sorted

  const filteredFiles = filterText
    ? searchMode === "content"
      ? contentMatches
        ? folderFiltered.filter((f) => contentMatches.has(f.path))
        : contentSearching ? [] : folderFiltered
      : folderFiltered.filter((f) => filterMatch(f.path, filterText))
    : folderFiltered

  const ragIncluded = files.filter((f) => f.include_rag === 1 && f.status === "complete").length
  const notIndexed = files.filter((f) => f.status === "not_indexed" || f.status === "pending").length
  const ragExcluded = files.filter((f) => f.include_rag === 0).length

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <FolderTree
        files={files}
        selectedFolder={selectedFolder}
        onSelectFolder={setSelectedFolder}
      />
      <div className="flex flex-col flex-1 min-w-0 min-h-0 gap-4 p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-lg font-semibold shrink-0">Browse MD Files</h2>
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                <div className="flex border rounded-md overflow-hidden h-9" role="group" aria-label="Search mode">
                  <button
                    type="button"
                    onClick={() => { setSearchMode("path"); clearMatches() }}
                    className={cn(
                      "px-2 flex items-center gap-1 text-xs cursor-pointer transition-colors",
                      searchMode === "path" ? "bg-primary text-primary-foreground" : "hover:bg-muted",
                    )}
                    aria-pressed={searchMode === "path"}
                    title="Filter by file path"
                  >
                    <Search className="h-3 w-3" />
                    Path
                  </button>
                  <button
                    type="button"
                    onClick={() => setSearchMode("content")}
                    className={cn(
                      "px-2 flex items-center gap-1 text-xs cursor-pointer transition-colors",
                      searchMode === "content" ? "bg-primary text-primary-foreground" : "hover:bg-muted",
                    )}
                    aria-pressed={searchMode === "content"}
                    title="Search file content (vector search)"
                  >
                    <FileText className="h-3 w-3" />
                    Content
                  </button>
                </div>
                <div className="relative">
                  {contentSearching ? (
                    <Loader2 className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground animate-spin" />
                  ) : (
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  )}
                  <Input
                    value={filterText}
                    onChange={(e) => setFilterText(e.target.value)}
                    placeholder={searchMode === "path" ? "Filter by path..." : "Search file content..."}
                    className="pl-8 pr-8 h-9 w-72"
                  />
                  {filterText && (
                    <button
                      type="button"
                      onClick={() => { setFilterText(""); clearMatches() }}
                      className="absolute right-2 top-2.5 text-muted-foreground hover:text-foreground"
                      aria-label="Clear filter"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
              <Button variant="outline" size="sm" className="cursor-pointer" onClick={() => indexAll()} disabled={isIndexing}>
                {isIndexing
                  ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                  : <FileDown className="h-3.5 w-3.5 mr-1.5" />
                }
                {isIndexing ? "Indexing..." : "Index All"}
              </Button>
              {selectedFolder && (
                <Button variant="outline" size="sm" className="cursor-pointer" onClick={() => setConfirmUnindexAll(true)}>
                  <FileX className="h-3.5 w-3.5 mr-1.5" />
                  Unindex Folder
                </Button>
              )}
              <Button variant="outline" size="sm" className="cursor-pointer" onClick={() => setAutoTagOpen(true)}>
                <Wand2 className="h-3.5 w-3.5 mr-1.5" />
                Auto-Tag
              </Button>
              <Button variant="outline" size="sm" className="cursor-pointer" onClick={handleRefresh} disabled={refreshing}>
                {refreshing
                  ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                  : <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                }
                {refreshing ? "Refreshing..." : "Refresh"}
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              {filterText
                ? searchMode === "content" && contentSearching
                  ? "Searching content..."
                  : `Showing ${filteredFiles.length} of ${folderFiltered.length} files${searchMode === "content" ? " (by content)" : ""}`
                : selectedFolder
                  ? `${folderFiltered.length} of ${files.length} files`
                  : `${files.length} files — ${ragIncluded} in RAG, ${notIndexed} not indexed${ragExcluded > 0 ? `, ${ragExcluded} excluded` : ""}`}
            </p>
          </div>
        </div>

        {/* Bulk action bar */}
        {selected.size > 0 && (
          <div className="flex items-center gap-3 px-3 py-2 bg-primary/5 border rounded-md -mt-2">
            <span className="text-sm font-medium">{selected.size} selected</span>
            <Button variant="outline" size="sm" className="cursor-pointer" onClick={() => setBulkTagOpen(true)}>
              <Tag className="h-3.5 w-3.5 mr-1.5" />
              Edit Tags
            </Button>
            <div className="flex-1" />
            <Button variant="ghost" size="sm" className="cursor-pointer" onClick={() => setSelected(new Set())}>
              <X className="h-3.5 w-3.5 mr-1.5" />
              Clear selection
            </Button>
          </div>
        )}

        <div className="flex-1 border rounded-md min-h-0 flex flex-col overflow-hidden">
          {/* Resizable header */}
          <div className="border-b bg-background sticky top-0 z-10 shrink-0">
            <ResizablePanelGroup
              orientation="horizontal"
              onLayoutChange={handleLayoutChange}
              className="h-10"
            >
              <ResizablePanel id="file" defaultSize={DEFAULT_LAYOUT.file} minSize={8}>
                <div className="flex items-center h-full">
                  <div className="pl-2 flex items-center" onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      aria-label="Select all files"
                      checked={filteredFiles.length > 0 && filteredFiles.every((f) => selected.has(f.path))}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          setSelected(new Set(filteredFiles.map((f) => f.path)))
                        } else {
                          setSelected(new Set())
                        }
                      }}
                    />
                  </div>
                  <SortHeader sortKey="file" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                    File
                  </SortHeader>
                </div>
              </ResizablePanel>
              <ResizableHandle />
              <ResizablePanel id="folder" defaultSize={DEFAULT_LAYOUT.folder} minSize={8}>
                <SortHeader sortKey="folder" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                  Folder
                </SortHeader>
              </ResizablePanel>
              <ResizableHandle />
              <ResizablePanel id="tags" defaultSize={DEFAULT_LAYOUT.tags} minSize={6}>
                <SortHeader sortKey="tags" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                  Tags
                </SortHeader>
              </ResizablePanel>
              <ResizableHandle />
              <ResizablePanel id="rag" defaultSize={DEFAULT_LAYOUT.rag} minSize={5}>
                <SortHeader sortKey="rag" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="justify-center">
                  Include RAG
                </SortHeader>
              </ResizablePanel>
              <ResizableHandle />
              <ResizablePanel id="status" defaultSize={DEFAULT_LAYOUT.status} minSize={5}>
                <SortHeader sortKey="status" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                  Status
                </SortHeader>
              </ResizablePanel>
              <ResizableHandle />
              <ResizablePanel id="chunks" defaultSize={DEFAULT_LAYOUT.chunks} minSize={4}>
                <SortHeader sortKey="chunks" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="justify-center">
                  Chunks
                </SortHeader>
              </ResizablePanel>
              <ResizableHandle />
              <ResizablePanel id="indexed" defaultSize={DEFAULT_LAYOUT.indexed} minSize={6}>
                <SortHeader sortKey="indexed" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                  Indexed At
                </SortHeader>
              </ResizablePanel>
              <ResizableHandle />
              <ResizablePanel id="actions" defaultSize={DEFAULT_LAYOUT.actions} minSize={8}>
                <div className="flex items-center px-2 h-full text-sm font-medium text-foreground">
                  Actions
                </div>
              </ResizablePanel>
            </ResizablePanelGroup>
          </div>

          {/* Virtualized scrollable body */}
          <VirtualizedFileList
            files={filteredFiles}
            allFilesEmpty={files.length === 0}
            busyPaths={busyPaths}
            gridTemplate={gridTemplate}
            selected={selected}
            onToggleSelect={toggleSelect}
            onToggleRag={toggleRag}
            onIndexFile={indexFile}
            onReindexFile={reindexFile}
            onUnindexFile={setPendingUnindex}
            onViewFile={setViewingPath}
            onUpdateTags={updateTags}
          />
        </div>

        <FileViewerDialog path={viewingPath} onClose={() => setViewingPath(null)} />
        <ConfirmDialog
          open={!!pendingUnindex}
          onOpenChange={(open) => { if (!open) setPendingUnindex(null) }}
          title="Remove from index?"
          description={`This will delete all chunks for "${pendingUnindex?.split("/").pop()}" from the vector store and exclude it from RAG.`}
          confirmLabel="Unindex"
          variant="destructive"
          onConfirm={async () => {
            if (pendingUnindex) {
              setPendingUnindex(null)
              await unindexFile(pendingUnindex)
            }
          }}
        />

        <ConfirmDialog
          open={confirmUnindexAll}
          onOpenChange={setConfirmUnindexAll}
          title="Unindex all files in folder?"
          description={`This will remove all indexed chunks for files under "${selectedFolder}" from the vector store.`}
          confirmLabel="Unindex All"
          variant="destructive"
          onConfirm={async () => {
            setConfirmUnindexAll(false)
            if (selectedFolder) await unindexSource(selectedFolder)
          }}
        />

        <BulkTagDialog
          open={bulkTagOpen}
          onOpenChange={setBulkTagOpen}
          selectedFiles={selected}
          allFiles={files}
          onApply={(paths, tags, mode) => {
            bulkUpdateTags(paths, tags, mode)
            setSelected(new Set())
          }}
        />

        <AutoTagDialog
          open={autoTagOpen}
          onOpenChange={setAutoTagOpen}
          sources={sources}
          onApplied={() => refresh()}
        />
      </div>
    </div>
  )
}
