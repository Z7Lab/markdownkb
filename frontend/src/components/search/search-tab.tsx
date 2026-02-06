import { useEffect } from "react"
import { useSearch } from "@/hooks/use-search"
import { SearchSidebar } from "./search-sidebar"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Markdown } from "@/components/ui/markdown"
import { Loader2, Search, Sparkles, Square } from "lucide-react"
import { useState, type KeyboardEvent } from "react"

export function SearchTab() {
  const {
    query, setQuery,
    folder, setFolder,
    tag, setTag,
    results, folders, tags,
    loading, error, search,
    searches, activeSearchId,
    deleteSearch, loadSearch,
    summary, summarySources, isSummarizing, stopSummary,
    newSearch,
  } = useSearch()

  const [viewingPath, setViewingPath] = useState<string | null>(null)

  // When a saved search is loaded, auto-run it
  const [pendingSearch, setPendingSearch] = useState(false)
  useEffect(() => {
    if (pendingSearch && query.trim()) {
      setPendingSearch(false)
      search()
    }
  }, [pendingSearch, query, search])

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") search()
  }

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <SearchSidebar
        searches={searches}
        activeSearchId={activeSearchId}
        onNewSearch={newSearch}
        onLoadSearch={(saved) => {
          loadSearch(saved)
          setPendingSearch(true)
        }}
        onDeleteSearch={deleteSearch}
      />

      <div className="flex flex-col flex-1 min-w-0 min-h-0 gap-4 p-4">
        {/* Search bar + filters */}
        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search your knowledge base..."
            className="flex-1"
          />
          <Select value={folder ?? "_all"} onValueChange={(v) => setFolder(v === "_all" ? null : v)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Folder" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">(all folders)</SelectItem>
              {folders.map((f) => (
                <SelectItem key={f} value={f}>{f}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={tag ?? "_all"} onValueChange={(v) => setTag(v === "_all" ? null : v)}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Tag" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">(all tags)</SelectItem>
              {tags.map((t) => (
                <SelectItem key={t} value={t}>{t}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={search} disabled={loading || !query.trim()}>
            <Search className="h-4 w-4 mr-1.5" />
            Search
          </Button>
        </div>

        {/* Results area */}
        <ScrollArea className="flex-1 min-h-0">
          <div className="space-y-3 pb-4">
            {error && (
              <p className="text-destructive text-center py-8">
                Search error: {error}
              </p>
            )}

            {/* AI Summary Card */}
            {(summary || isSummarizing) && (
              <Card className="border-primary/30 bg-primary/5">
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Sparkles className="h-4 w-4 text-primary" />
                    <span className="text-sm font-semibold text-primary">AI Summary</span>
                    {isSummarizing && (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-5 w-5 ml-auto"
                          onClick={stopSummary}
                          aria-label="Stop summary"
                        >
                          <Square className="h-3 w-3" />
                        </Button>
                      </>
                    )}
                  </div>
                  <Markdown className="text-sm">{summary || "Generating summary..."}</Markdown>
                  {summarySources.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-3 pt-3 border-t">
                      {summarySources.map((src) => (
                        <Badge
                          key={src}
                          variant="outline"
                          className="cursor-pointer hover:bg-accent text-xs"
                          onClick={() => setViewingPath(src)}
                        >
                          {src.split("/").pop()}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Result cards */}
            {results.length === 0 && !loading && !error && !summary && (
              <p className="text-muted-foreground text-center py-8">
                {query ? "No results found." : "Enter a query to search."}
              </p>
            )}
            {results.map((r, i) => (
              <Card
                key={`${r.metadata.source_path ?? ""}:${r.score}:${i}`}
                className="cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={() => setViewingPath(r.metadata.source_path ?? null)}
              >
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge variant="secondary">
                      Relevance: {Math.round(r.score * 100)}%
                    </Badge>
                    <span className="text-sm font-mono text-muted-foreground truncate">
                      {r.metadata.source_path ?? "unknown"}
                    </span>
                    {r.metadata.heading && (
                      <span className="text-sm text-muted-foreground">
                        | {r.metadata.heading}
                      </span>
                    )}
                  </div>
                  <Markdown className="text-sm">
                    {r.document.length > 500 ? r.document.slice(0, 500) + "..." : r.document}
                  </Markdown>
                </CardContent>
              </Card>
            ))}
          </div>
        </ScrollArea>
      </div>

      <FileViewerDialog
        path={viewingPath}
        onClose={() => setViewingPath(null)}
      />
    </div>
  )
}
