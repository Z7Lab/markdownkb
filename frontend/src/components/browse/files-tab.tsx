import { useState } from "react"
import { useFiles } from "@/hooks/use-files"
import { useTableSort } from "@/hooks/use-table-sort"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { FolderTree } from "./folder-tree"
import { FileRow } from "./file-row"
import { Input } from "@/components/ui/input"
import {
  TableBody,
  TableCell,
  TableRow,
} from "@/components/ui/table"
import { SortableTableHead } from "@/components/ui/sortable-table-head"
import { RefreshCw, Search, X } from "lucide-react"
import type { TrackedFile } from "@/lib/types"
import { basename, dirname } from "@/lib/utils"

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

export function FilesTab() {
  const { files, busyPaths, refresh, toggleRag, unindexFile, indexFile, reindexFile } = useFiles()
  const [filterText, setFilterText] = useState("")
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null)
  const [viewingPath, setViewingPath] = useState<string | null>(null)
  const [pendingUnindex, setPendingUnindex] = useState<string | null>(null)
  const { sorted, sortKey, sortDir, onSort } = useTableSort(files, getValue)

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

        <div className="flex-1 border rounded-md min-h-0 overflow-auto">
          <table className="w-full caption-bottom text-sm relative">
            <thead className="[&_tr]:border-b">
              <TableRow className="border-b">
                <SortableTableHead sortKey="file" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="sticky top-0 bg-background z-10">
                  File
                </SortableTableHead>
                <SortableTableHead sortKey="folder" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="sticky top-0 bg-background z-10">
                  Folder
                </SortableTableHead>
                <SortableTableHead sortKey="rag" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="text-center sticky top-0 bg-background z-10">
                  Include RAG
                </SortableTableHead>
                <SortableTableHead sortKey="status" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="sticky top-0 bg-background z-10">
                  Status
                </SortableTableHead>
                <SortableTableHead sortKey="chunks" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="text-center sticky top-0 bg-background z-10">
                  Chunks
                </SortableTableHead>
                <SortableTableHead sortKey="" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="sticky top-0 bg-background z-10">
                  Actions
                </SortableTableHead>
              </TableRow>
            </thead>
            <TableBody>
              {filteredFiles.map((f) => (
                <FileRow
                  key={f.path}
                  file={f}
                  busy={busyPaths.has(f.path)}
                  onToggleRag={toggleRag}
                  onIndexFile={indexFile}
                  onReindexFile={reindexFile}
                  onUnindexFile={setPendingUnindex}
                  onViewFile={setViewingPath}
                />
              ))}
              {filteredFiles.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                    {files.length === 0 ? "No markdown files found in watch directories." : "No files match your filter."}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </table>
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
      </div>
    </div>
  )
}
