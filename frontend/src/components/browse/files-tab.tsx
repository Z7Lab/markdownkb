import { useCallback, useEffect, useRef, useState } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { useFiles } from "@/hooks/use-files"
import { useSettings } from "@/hooks/use-settings"
import { useTableSort } from "@/hooks/use-table-sort"
import { useFileFilter, getValue } from "@/hooks/use-file-filter"
import { useUrlSearchParam } from "@/hooks/use-url-search-param"
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
import { cn } from "@/lib/utils"

// Column IDs and default sizes as percentages (must sum to 100)
const BASE_COL_IDS = ["file", "folder", "tags", "rag", "status", "chunks", "indexed", "actions"]
const BASE_LAYOUT: Record<string, number> = {
  file: 20, folder: 20, tags: 12, rag: 8, status: 8, chunks: 6, indexed: 12, actions: 14,
}
const KG_COL_IDS = ["file", "folder", "tags", "rag", "status", "chunks", "entities", "indexed", "actions"]
const KG_LAYOUT: Record<string, number> = {
  file: 18, folder: 18, tags: 11, rag: 7, status: 7, chunks: 5, entities: 6, indexed: 11, actions: 17,
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
  kgEnabled,
  onExtractEntities,
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
  kgEnabled: boolean
  onExtractEntities: (path: string) => void
}) {
  const parentRef = useRef<HTMLDivElement>(null)

  // eslint-disable-next-line react-hooks/incompatible-library -- @tanstack/react-virtual v3 peer-deps lag behind React 19; safe to use
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
                kgEnabled={kgEnabled}
                onExtractEntities={onExtractEntities}
                onUpdateTags={onUpdateTags}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}

// TODO: Extract toolbar/action bar into sub-component, filtering logic into
// a dedicated hook, and move dialog state closer to dialogs to reduce complexity.
export function FilesTab() {
  const { files, busyPaths, refresh, toggleRag, unindexFile, indexFile, reindexFile, indexAll, unindexSource, updateTags, bulkUpdateTags, extractEntities } = useFiles()
  const { settings } = useSettings()
  const kgEnabled = !!settings?.plugins_enabled?.knowledge_graph
  const COL_IDS = kgEnabled ? KG_COL_IDS : BASE_COL_IDS
  const DEFAULT_LAYOUT = kgEnabled ? KG_LAYOUT : BASE_LAYOUT
  const { isIndexing, lastIndexedAt } = useIndexEvents()
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
  const [viewingPath, setViewingPath] = useUrlSearchParam("file")
  const [pendingUnindex, setPendingUnindex] = useState<string | null>(null)
  const [confirmUnindexAll, setConfirmUnindexAll] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkTagOpen, setBulkTagOpen] = useState(false)
  const [autoTagOpen, setAutoTagOpen] = useState(false)
  const [sources, setSources] = useState<string[]>([])
  const { sorted, sortKey, sortDir, onSort } = useTableSort(files, getValue)
  const { filterText, setFilterText, searchMode, setSearchMode, contentSearching, clearMatches, folderFiltered, filteredFiles } = useFileFilter(sorted, selectedFolder)

  // Column sizes as percentages (synced from ResizablePanelGroup)
  const [colLayout, setColLayout] = useState(DEFAULT_LAYOUT)
  const handleLayoutChange = useCallback((layout: Record<string, number>) => {
    setColLayout(layout)
  }, [])
  const gridTemplate = COL_IDS.map((id) => `${colLayout[id] ?? 16}%`).join(" ")

  // Fetch sources for auto-tag dialog
  useEffect(() => {
    api.get<{ sources: string[] }>("/api/v1/sources").then((res) => setSources(res.sources)).catch(() => { /* sources list for auto-tag is non-critical */ })
  }, [])

  const toggleSelect = useCallback((path: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }, [])

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
          <div className="border-b bg-background sticky top-0 z-10 shrink-0 overflow-hidden">
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
              {kgEnabled && (
                <>
                  <ResizablePanel id="entities" defaultSize={DEFAULT_LAYOUT.entities} minSize={4}>
                    <SortHeader sortKey="entities" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="justify-center">
                      Entities
                    </SortHeader>
                  </ResizablePanel>
                  <ResizableHandle />
                </>
              )}
              <ResizablePanel id="indexed" defaultSize={DEFAULT_LAYOUT.indexed} minSize={6}>
                <SortHeader sortKey="indexed" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                  Last Indexed
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
            kgEnabled={kgEnabled}
            onExtractEntities={extractEntities}
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
