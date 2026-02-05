import { useFiles } from "@/hooks/use-files"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { RefreshCw } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { cn } from "@/lib/utils"

function basename(path: string) {
  return path.split("/").pop() ?? path
}

function dirname(path: string) {
  const parts = path.split("/")
  parts.pop()
  return parts.join("/") || "/"
}

export function BrowseTab() {
  const { files, selectedFile, content, loading, refresh, selectFile, toggleRag } = useFiles()

  const isIncluded = selectedFile?.status !== "excluded"

  return (
    <div className="flex flex-col h-[calc(100vh-4.5rem)] gap-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Browse Knowledge Base</h2>
        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
          Refresh
        </Button>
      </div>

      <ScrollArea className="h-[30vh] border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>File</TableHead>
              <TableHead>Folder</TableHead>
              <TableHead>RAG</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Chunks</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {files.map((f) => (
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
            {files.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                  No files indexed yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </ScrollArea>

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
    </div>
  )
}
