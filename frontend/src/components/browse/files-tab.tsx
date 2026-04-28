import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"
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
import { AlertCircle, FileDown, FileText, FileX, FilePlus, Loader2, RefreshCw, Search, Tag, Wand2, X } from "lucide-react"
import { SortButton } from "@/components/ui/table"
import type { TrackedFile } from "@/lib/types"
import { cn } from "@/lib/utils"

// Column IDs and default sizes as percentages (must sum to 100)
const BASE_COL_IDS = ["file", "folder", "tags", "include", "status", "chunks", "indexed", "actions"]
const BASE_LAYOUT: Record<string, number> = {
  file: 20, folder: 20, tags: 12, include: 8, status: 8, chunks: 6, indexed: 12, actions: 14,
}
const KG_COL_IDS = ["file", "folder", "tags", "include", "status", "chunks", "entities", "indexed", "actions"]
const KG_LAYOUT: Record<string, number> = {
  file: 18, folder: 18, tags: 11, include: 7, status: 7, chunks: 5, entities: 6, indexed: 11, actions: 17,
}

function SortHeader(props: React.ComponentProps<typeof SortButton>) {
  return <SortButton {...props} className={cn("px-2 h-full text-sm", props.className)} />
}

/** Virtualized file list — only renders visible rows for large file sets */
function VirtualizedFileList({
  files,
  allFilesEmpty,
  busyPaths,
  gridTemplate,
  selected,
  onToggleSelect,
  onToggleIndex,
  onIndexFile,
  onReindexFile,
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
  onToggleIndex: (path: string, checked: boolean) => void
  onIndexFile: (path: string) => void
  onReindexFile: (path: string) => void
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
          if (!f) return null
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
                onToggleIndex={onToggleIndex}
                onIndexFile={onIndexFile}
                onReindexFile={onReindexFile}
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

// Refactor target: extract toolbar into sub-component, filtering into a hook,
// and colocate dialog state with dialogs. Tracked in the frontend review backlog.
export function FilesTab() {
  const { files, busyPaths, refresh, toggleIndex, indexFile, reindexFile, indexAll, unindexSource, updateTags, bulkUpdateTags, extractEntities } = useFiles()
  const { settings } = useSettings()
  const kgEnabled = !!settings?.plugins_enabled?.knowledge_graph
  const converterEnabled = !!settings?.plugins_enabled?.converter
  const COL_IDS = kgEnabled ? KG_COL_IDS : BASE_COL_IDS
  const DEFAULT_LAYOUT = kgEnabled ? KG_LAYOUT : BASE_LAYOUT
  const { isIndexing, lastIndexedAt } = useIndexEvents()
  const [refreshing, setRefreshing] = useState(false)
  const [importing, setImporting] = useState(false)
  const importInputRef = useRef<HTMLInputElement>(null)

  const handleImport = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ""
    setImporting(true)
    try {
      const fd = new FormData()
      fd.append("file", file)
      const result = await api.upload<{ filename: string }>("/api/v1/converter/ingest", fd)
      toast.success(`Imported "${result.filename}" into knowledge base`)
      await refresh()
    } catch (err) {
      toast.error((err as Error).message || "Import failed")
    } finally {
      setImporting(false)
    }
  }, [refresh])

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

  const indexIncluded = files.filter((f) => f.include_in_index === 1 && f.status === "complete").length
  const notIndexed = files.filter((f) => f.status === "not_indexed" || f.status === "pending").length
  const indexExcluded = files.filter((f) => f.include_in_index === 0).length
  const errorCount = files.filter((f) => f.status === "error").length

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
              {converterEnabled && (
                <>
                  <input
                    ref={importInputRef}
                    type="file"
                    className="hidden"
                    onChange={handleImport}
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    className="cursor-pointer"
                    onClick={() => importInputRef.current?.click()}
                    disabled={importing}
                    title="Convert and import a document (PDF, DOCX, etc.) into your knowledge base"
                  >
                    {importing
                      ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                      : <FilePlus className="h-3.5 w-3.5 mr-1.5" />
                    }
                    {importing ? "Importing..." : "Import File"}
                  </Button>
                </>
              )}
              {errorCount > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  className="cursor-pointer border-destructive/50 text-destructive hover:bg-destructive/10"
                  onClick={() => indexAll()}
                  disabled={isIndexing}
                  title="Retry all errored files"
                >
                  <AlertCircle className="h-3.5 w-3.5 mr-1.5" />
                  Retry {errorCount} error{errorCount !== 1 ? "s" : ""}
                </Button>
              )}
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
                  : `${files.length} files — ${indexIncluded} indexed, ${notIndexed} not indexed${indexExcluded > 0 ? `, ${indexExcluded} excluded` : ""}${errorCount > 0 ? `, ${errorCount} errored` : ""}`}
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
                  {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- stopPropagation wrapper around the select-all Checkbox; role=group is correct */}
                  <div className="pl-2 flex items-center" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()} role="group">
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
              <ResizablePanel id="include" defaultSize={DEFAULT_LAYOUT.include} minSize={5}>
                <SortHeader sortKey="include" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="justify-center">
                  Include
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
            onToggleIndex={toggleIndex}
            onIndexFile={indexFile}
            onReindexFile={reindexFile}
            onViewFile={setViewingPath}
            onUpdateTags={updateTags}
            kgEnabled={kgEnabled}
            onExtractEntities={extractEntities}
          />
        </div>

        <FileViewerDialog path={viewingPath} onClose={() => setViewingPath(null)} />
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
