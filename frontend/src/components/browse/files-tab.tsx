import { useCallback, useEffect, useState } from "react"
import { useFiles } from "@/hooks/use-files"
import { useTableSort } from "@/hooks/use-table-sort"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { useIndexEvents } from "@/hooks/use-index-events"
import { FolderTree } from "./folder-tree"
import { FileRow } from "./file-row"
import { Input } from "@/components/ui/input"
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable"
import { ArrowDown, ArrowUp, FileDown, FileX, Loader2, RefreshCw, Search, X } from "lucide-react"
import type { TrackedFile } from "@/lib/types"
import { basename, dirname, cn } from "@/lib/utils"

/** VSCode-style fuzzy match: characters must appear in order but not contiguous */
function fuzzyMatch(text: string, pattern: string): boolean {
  const textLower = text.toLowerCase()
  const patternLower = pattern.toLowerCase()
  let ti = 0
  for (let pi = 0; pi < patternLower.length; pi++) {
    const idx = textLower.indexOf(patternLower[pi], ti)
    if (idx === -1) return false
    ti = idx + 1
  }
  return true
}

/** If pattern is "quoted", do exact substring match; otherwise fuzzy */
function filterMatch(text: string, pattern: string): boolean {
  if (pattern.startsWith('"') && pattern.endsWith('"') && pattern.length > 2) {
    const exact = pattern.slice(1, -1).toLowerCase()
    return text.toLowerCase().includes(exact)
  }
  return fuzzyMatch(text, pattern)
}

const getValue = (f: TrackedFile, key: string): string | number | null => {
  switch (key) {
    case "file":
      return basename(f.path)
    case "folder":
      return dirname(f.path)
    case "rag":
      return f.include_rag
    case "status":
      return f.status
    case "chunks":
      return f.chunk_count
    default:
      return null
  }
}

// Column IDs and default sizes as percentages (must sum to 100)
const COL_IDS = ["file", "folder", "rag", "status", "chunks", "actions"] as const
const DEFAULT_LAYOUT: Record<string, number> = {
  file: 25, folder: 25, rag: 12, status: 12, chunks: 10, actions: 16,
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
        "flex items-center gap-1 px-2 h-full text-sm font-medium text-foreground cursor-pointer select-none whitespace-nowrap",
        className,
      )}
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

export function FilesTab() {
  const { files, busyPaths, refresh, toggleRag, unindexFile, indexFile, reindexFile, indexAll, unindexSource } = useFiles()
  const { isIndexing, lastIndexedAt } = useIndexEvents()
  const [filterText, setFilterText] = useState("")

  // Auto-refresh file list when indexing events arrive
  useEffect(() => {
    if (lastIndexedAt) refresh(true)
  }, [lastIndexedAt, refresh])
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null)
  const [viewingPath, setViewingPath] = useState<string | null>(null)
  const [pendingUnindex, setPendingUnindex] = useState<string | null>(null)
  const [confirmUnindexAll, setConfirmUnindexAll] = useState(false)
  const { sorted, sortKey, sortDir, onSort } = useTableSort(files, getValue)

  // Column sizes as percentages (synced from ResizablePanelGroup)
  const [colLayout, setColLayout] = useState(DEFAULT_LAYOUT)
  const handleLayoutChange = useCallback((layout: Record<string, number>) => {
    setColLayout(layout)
  }, [])
  const gridTemplate = COL_IDS.map((id) => `${colLayout[id] ?? 16}%`).join(" ")

  const folderFiltered = selectedFolder
    ? sorted.filter((f) => {
        const dir = dirname(f.path)
        return dir === selectedFolder || dir.startsWith(selectedFolder + "/")
      })
    : sorted

  const filteredFiles = filterText
    ? folderFiltered.filter((f) => filterMatch(f.path, filterText))
    : folderFiltered

  const ragIncluded = files.filter((f) => f.include_rag === 1 && f.status !== "not_indexed").length
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
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  value={filterText}
                  onChange={(e) => setFilterText(e.target.value)}
                  placeholder='Fuzzy filter or "exact match"'
                  className="pl-8 pr-8 h-9 w-72"
                />
                {filterText && (
                  <button
                    type="button"
                    onClick={() => setFilterText("")}
                    className="absolute right-2 top-2.5 text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
              <Button variant="outline" size="sm" onClick={() => indexAll()} disabled={isIndexing}>
                {isIndexing
                  ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                  : <FileDown className="h-3.5 w-3.5 mr-1.5" />
                }
                {isIndexing ? "Indexing..." : "Index All"}
              </Button>
              {selectedFolder && (
                <Button variant="outline" size="sm" onClick={() => setConfirmUnindexAll(true)}>
                  <FileX className="h-3.5 w-3.5 mr-1.5" />
                  Unindex Folder
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => refresh()}>
                <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                Refresh
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              {filterText
                ? `Showing ${filteredFiles.length} of ${folderFiltered.length} files`
                : selectedFolder
                  ? `${folderFiltered.length} of ${files.length} files`
                  : `${files.length} files — ${ragIncluded} in RAG, ${notIndexed} not indexed${ragExcluded > 0 ? `, ${ragExcluded} excluded` : ""}`}
            </p>
          </div>
        </div>

        <div className="flex-1 border rounded-md min-h-0 flex flex-col overflow-hidden">
          {/* Resizable header */}
          <div className="border-b bg-background sticky top-0 z-10 shrink-0">
            <ResizablePanelGroup
              orientation="horizontal"
              onLayoutChange={handleLayoutChange}
              className="h-10"
            >
              <ResizablePanel id="file" defaultSize={DEFAULT_LAYOUT.file} minSize={8}>
                <SortHeader sortKey="file" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                  File
                </SortHeader>
              </ResizablePanel>
              <ResizableHandle />
              <ResizablePanel id="folder" defaultSize={DEFAULT_LAYOUT.folder} minSize={8}>
                <SortHeader sortKey="folder" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                  Folder
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
              <ResizablePanel id="actions" defaultSize={DEFAULT_LAYOUT.actions} minSize={8}>
                <div className="flex items-center px-2 h-full text-sm font-medium text-foreground">
                  Actions
                </div>
              </ResizablePanel>
            </ResizablePanelGroup>
          </div>

          {/* Scrollable body */}
          <div className="flex-1 overflow-auto min-h-0">
            {filteredFiles.map((f) => (
              <FileRow
                key={f.path}
                file={f}
                busy={busyPaths.has(f.path)}
                gridTemplate={gridTemplate}
                onToggleRag={toggleRag}
                onIndexFile={indexFile}
                onReindexFile={reindexFile}
                onUnindexFile={setPendingUnindex}
                onViewFile={setViewingPath}
              />
            ))}
            {filteredFiles.length === 0 && (
              <div className="text-center text-muted-foreground py-8">
                {files.length === 0 ? "No markdown files found in watch directories." : "No files match your filter."}
              </div>
            )}
          </div>
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
      </div>
    </div>
  )
}
