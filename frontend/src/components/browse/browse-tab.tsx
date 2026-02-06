import { useState } from "react"
import { useFiles } from "@/hooks/use-files"
import { useTableSort } from "@/hooks/use-table-sort"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { FolderTree } from "./folder-tree"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { SortableTableHead } from "@/components/ui/sortable-table-head"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Plus, RefreshCw, Search, Trash2, X } from "lucide-react"
import type { TrackedFile } from "@/lib/types"

function basename(path: string) {
  return path.split("/").pop() ?? path
}

function dirname(path: string) {
  const parts = path.split("/")
  parts.pop()
  return parts.join("/") || "/"
}

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

export function BrowseTab() {
  const { files, loading, refresh, toggleRag, unindexFile, indexFile, reindexFile } = useFiles()
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
              <Button variant="outline" size="sm" onClick={refresh}>
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

        <div className="flex-1 border rounded-md overflow-hidden min-h-0">
          <ScrollArea className="h-full">
            <Table>
              <TableHeader className="sticky top-0 bg-background z-10">
                <TableRow>
                  <SortableTableHead sortKey="file" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                    File
                  </SortableTableHead>
                  <SortableTableHead sortKey="folder" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                    Folder
                  </SortableTableHead>
                  <SortableTableHead sortKey="rag" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="text-center">
                    Include RAG
                  </SortableTableHead>
                  <SortableTableHead sortKey="status" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                    Status
                  </SortableTableHead>
                  <SortableTableHead sortKey="chunks" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="text-center">
                    Chunks
                  </SortableTableHead>
                  <SortableTableHead sortKey="" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                    Actions
                  </SortableTableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredFiles.map((f) => {
                  const isIndexed = f.status === "complete"
                  const isNotIndexed = f.status === "not_indexed" || f.status === "pending"
                  const ragOn = f.include_rag === 1

                  return (
                    <TableRow
                      key={f.path}
                      className="cursor-pointer"
                      onClick={() => setViewingPath(f.path)}
                    >
                      <TableCell className="font-mono text-sm truncate max-w-[200px]">
                        {basename(f.path)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground truncate max-w-[180px]">
                        {dirname(f.path)}
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-center">
                          <Switch
                            checked={ragOn}
                            disabled={loading || f.status === "not_indexed"}
                            onClick={(e) => e.stopPropagation()}
                            onCheckedChange={(checked) => toggleRag(f.path, checked)}
                          />
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">
                        {f.status === "not_indexed" ? (
                          <span className="text-muted-foreground">not indexed</span>
                        ) : f.status === "indexing" ? (
                          <span className="text-blue-500">indexing</span>
                        ) : f.status === "error" ? (
                          <span className="text-destructive">error</span>
                        ) : f.status}
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-center">{f.chunk_count}</div>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                          {isNotIndexed && ragOn && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7"
                                  disabled={loading}
                                  onClick={() => indexFile(f.path)}
                                >
                                  <Plus className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Index this file</TooltipContent>
                            </Tooltip>
                          )}
                          {isIndexed && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7"
                                  disabled={loading}
                                  onClick={() => reindexFile(f.path)}
                                >
                                  <RefreshCw className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Re-index this file</TooltipContent>
                            </Tooltip>
                          )}
                          {(isIndexed || f.status === "error") && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7 text-destructive hover:text-destructive"
                                  disabled={loading}
                                  onClick={() => setPendingUnindex(f.path)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>Remove from index</TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
                {filteredFiles.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      {files.length === 0 ? "No markdown files found in watch directories." : "No files match your filter."}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </ScrollArea>
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
