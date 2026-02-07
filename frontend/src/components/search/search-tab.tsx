import { useSearch } from "@/hooks/use-search"
import { SearchSidebar } from "./search-sidebar"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Markdown } from "@/components/ui/markdown"
import { Loader2, Search, Sparkles, Square, RotateCcw, Clock, AlertCircle } from "lucide-react"
import { useState, type KeyboardEvent } from "react"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

// ASCII art banner
const ASCII_BANNER = `
███╗   ███╗██████╗ ██╗  ██╗██████╗     ███████╗███████╗ █████╗ ██████╗  ██████╗██╗  ██╗
████╗ ████║██╔══██╗██║ ██╔╝██╔══██╗    ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝██║  ██║
██╔████╔██║██║  ██║█████╔╝ ██████╔╝    ███████╗█████╗  ███████║██████╔╝██║     ███████║
██║╚██╔╝██║██║  ██║██╔═██╗ ██╔══██╗    ╚════██║██╔══╝  ██╔══██║██╔══██╗██║     ██╔══██║
██║ ╚═╝ ██║██████╔╝██║  ██╗██████╔╝    ███████║███████╗██║  ██║██║  ██║╚██████╗██║  ██║
╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝╚═════╝     ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
`.trim()

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
    isHistorical,
    resultsChanged,
    missingFiles,
    newFiles,
    storedResultCount,
    currentResultCount,
    createdAt,
    requery,
  } = useSearch()

  const [viewingPath, setViewingPath] = useState<string | null>(null)

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") search()
  }

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <SearchSidebar
        searches={searches}
        activeSearchId={activeSearchId}
        folders={folders}
        tags={tags}
        selectedFolder={folder}
        selectedTag={tag}
        onNewSearch={newSearch}
        onLoadSearch={loadSearch}
        onDeleteSearch={deleteSearch}
        onFolderChange={setFolder}
        onTagChange={setTag}
      />

      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        {/* Empty state - positioned higher on screen */}
        {results.length === 0 && !summary && !loading && (
          <div className="flex flex-col items-center justify-start flex-1 gap-6 p-4 pt-[20vh]">
            {/* ASCII Art Banner */}
            <pre className="text-[0.45rem] leading-[0.6rem] text-primary/80 font-mono whitespace-pre">
              {ASCII_BANNER}
            </pre>

            {/* Search bar */}
            <div className="flex gap-2 w-full max-w-2xl">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search your knowledge base..."
                className="flex-1"
              />
              <Button onClick={search} disabled={loading || !query.trim()}>
                <Search className="h-4 w-4 mr-1.5" />
                Search
              </Button>
            </div>
          </div>
        )}

        {/* Results area - show when loading or have results/summary */}
        {(results.length > 0 || summary || loading) && (
          <ScrollArea className="flex-1 min-h-0">
            <div className="space-y-3 p-4 pb-4">
            {/* Query header - show the search query prominently */}
            {query && (
              <div className="flex flex-col gap-2 pb-2 border-b">
                <div className="flex items-center gap-2">
                  <Search className="h-4 w-4 text-muted-foreground" />
                  <h2 className="text-base font-semibold text-foreground">
                    {query}
                  </h2>

                  {/* Historical vs Live badge */}
                  <Badge variant={isHistorical ? "secondary" : "default"} className="text-xs">
                    {isHistorical ? "Historical" : "Live"}
                  </Badge>

                  {/* Folder/Tag filters */}
                  {(folder || tag) && (
                    <div className="flex items-center gap-1">
                      {folder && (
                        <Badge variant="outline" className="text-xs">
                          📁 {folder.split("/").pop()}
                        </Badge>
                      )}
                      {tag && (
                        <Badge variant="outline" className="text-xs">
                          🏷️ {tag}
                        </Badge>
                      )}
                    </div>
                  )}

                  {/* Re-query button (only for historical searches) */}
                  {isHistorical && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="outline"
                          size="sm"
                          className="ml-auto h-7 px-2"
                          onClick={requery}
                          disabled={loading}
                        >
                          <RotateCcw className="h-3.5 w-3.5 mr-1" />
                          Re-query
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        Run this query again with current KB state and generate a new AI summary
                      </TooltipContent>
                    </Tooltip>
                  )}
                </div>

                {/* Historical metadata and diff indicators */}
                {isHistorical && (
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    {createdAt && (
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        <span>
                          {new Date(createdAt).toLocaleString()}
                        </span>
                      </div>
                    )}
                    {resultsChanged && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="flex items-center gap-2">
                            <AlertCircle className="h-3 w-3 text-amber-500" />
                            <span className="text-amber-600 dark:text-amber-400">
                              Results changed
                            </span>
                            {storedResultCount !== undefined && currentResultCount !== undefined && (
                              <Badge variant="outline" className="text-xs">
                                {storedResultCount} → {currentResultCount}
                              </Badge>
                            )}
                          </div>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <div className="space-y-1">
                            <p>The knowledge base has changed since this search was created.</p>
                            {missingFiles.length > 0 && (
                              <p className="text-destructive">
                                {missingFiles.length} file{missingFiles.length > 1 ? "s" : ""} removed from RAG
                              </p>
                            )}
                            {newFiles.length > 0 && (
                              <p className="text-green-500">
                                {newFiles.length} new file{newFiles.length > 1 ? "s" : ""} added to RAG
                              </p>
                            )}
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Loading spinner */}
            {loading && results.length === 0 && !summary && (
              <div className="flex flex-col items-center justify-center py-20 gap-3">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">
                  Searching your knowledge base...
                </p>
              </div>
            )}

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

            {/* Empty state - only show after search with no results */}
            {results.length === 0 && !loading && !error && !summary && query && (
              <p className="text-muted-foreground text-center py-8">
                No results found for "{query}"
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
        )}
      </div>

      <FileViewerDialog
        path={viewingPath}
        onClose={() => setViewingPath(null)}
      />
    </div>
  )
}
