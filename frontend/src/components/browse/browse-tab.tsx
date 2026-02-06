import { useState } from "react"
import { useFiles } from "@/hooks/use-files"
import { useTableSort } from "@/hooks/use-table-sort"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
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
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Plus, RefreshCw, Search, Trash2 } from "lucide-react"
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
  const [viewingPath, setViewingPath] = useState<string | null>(null)
  const [pendingUnindex, setPendingUnindex] = useState<string | null>(null)
  const { sorted, sortKey, sortDir, onSort } = useTableSort(files, getValue)

  const filteredFiles = filterText
    ? sorted.filter((f) => fuzzyMatch(f.path, filterText))
    : sorted

  return (
    <div className="flex flex-col h-full gap-4 p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold shrink-0">Browse MD Files</h2>
        <div className="flex flex-col items-end gap-1">
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                placeholder="Filter by file or folder..."
                className="pl-8 h-9 w-56"
              />
            </div>
            <Button variant="outline" size="sm" onClick={refresh}>
              <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
              Refresh
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            {filterText
              ? `Showing ${filteredFiles.length} of ${files.length} files`
              : `${files.length} files`}
          </p>
        </div>
      </div>

      <div className="flex-1 border rounded-md overflow-hidden min-h-0">
        <ScrollArea className="h-full">
          <TooltipProvider delayDuration={300}>
          <Table>
            <TableHeader className="sticky top-0 bg-background z-10">
              <TableRow>
                <SortableTableHead sortKey="file" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                  File
                </SortableTableHead>
                <SortableTableHead sortKey="folder" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                  Folder
                </SortableTableHead>
                <SortableTableHead sortKey="rag" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                  Include RAG
                </SortableTableHead>
                <SortableTableHead sortKey="status" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                  Status
                </SortableTableHead>
                <SortableTableHead sortKey="chunks" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="text-right">
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
                      <Switch
                        checked={ragOn}
                        disabled={loading || f.status === "not_indexed"}
                        onClick={(e) => e.stopPropagation()}
                        onCheckedChange={(checked) => toggleRag(f.path, checked)}
                      />
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
                    <TableCell className="text-right">{f.chunk_count}</TableCell>
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
          </TooltipProvider>
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
  )
}
