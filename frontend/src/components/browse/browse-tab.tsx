import { useState } from "react"
import { useFiles } from "@/hooks/use-files"
import { useTableSort } from "@/hooks/use-table-sort"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { SortableTableHead } from "@/components/ui/sortable-table-head"
import { Badge } from "@/components/ui/badge"
import { RefreshCw, Search } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { cn } from "@/lib/utils"
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
      return f.status === "excluded" ? 0 : 1
    case "status":
      return f.status
    case "chunks":
      return f.chunk_count
    default:
      return null
  }
}

export function BrowseTab() {
  const { files, selectedFile, content, loading, pendingExclude, refresh, selectFile, toggleRag, confirmExclude, setPendingExclude } = useFiles()
  const [filterText, setFilterText] = useState("")
  const { sorted, sortKey, sortDir, onSort } = useTableSort(files, getValue)

  const filteredFiles = filterText
    ? sorted.filter((f) => fuzzyMatch(f.path, filterText))
    : sorted

  const isIncluded = selectedFile?.status !== "excluded"

  return (
    <div className="flex flex-col h-full gap-4 p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold shrink-0">Browse Knowledge Base</h2>
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

      <div className="h-[30vh] border rounded-md overflow-hidden flex flex-col">
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
                RAG
              </SortableTableHead>
              <SortableTableHead sortKey="status" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort}>
                Status
              </SortableTableHead>
              <SortableTableHead sortKey="chunks" activeSortKey={sortKey} sortDir={sortDir} onSort={onSort} className="text-right">
                Chunks
              </SortableTableHead>
            </TableRow>
          </TableHeader>
        </Table>
        <ScrollArea className="flex-1">
          <Table>
            <TableBody>
              {filteredFiles.map((f) => (
                <TableRow
                  key={f.path}
                  className={cn(
                    "cursor-pointer",
                    selectedFile?.path === f.path && "bg-muted",
                  )}
                  onClick={() => selectFile(f)}
                >
                  <TableCell className="font-mono text-sm truncate max-w-[200px]">
                    {basename(f.path)}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground truncate max-w-[180px]">
                    {dirname(f.path)}
                  </TableCell>
                  <TableCell>
                    <Badge variant={f.status === "excluded" ? "destructive" : "default"}>
                      {f.status === "excluded" ? "No" : "Yes"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm">{f.status}</TableCell>
                  <TableCell className="text-right">{f.chunk_count}</TableCell>
                </TableRow>
              ))}
              {filteredFiles.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                    {files.length === 0 ? "No files indexed yet." : "No files match your filter."}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </ScrollArea>
      </div>

      {selectedFile && (
        <div className="flex flex-col flex-1 gap-3 min-h-0">
          <div className="flex items-center gap-4">
            <span className="font-mono text-sm truncate flex-1">
              {selectedFile.path}
            </span>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={isIncluded}
                disabled={loading}
                onCheckedChange={(checked) =>
                  toggleRag(selectedFile, checked === true)
                }
              />
              Include in RAG
            </label>
          </div>
          <ScrollArea className="flex-1 border rounded-md p-4">
            <div className="mdkb-prose">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          </ScrollArea>
        </div>
      )}
      <ConfirmDialog
        open={!!pendingExclude}
        onOpenChange={(open) => { if (!open) setPendingExclude(null) }}
        title="Remove from RAG index?"
        description={`This will remove "${pendingExclude?.path.split("/").pop()}" from the vector store and exclude it from future indexing.`}
        confirmLabel="Remove"
        onConfirm={confirmExclude}
      />
    </div>
  )
}
