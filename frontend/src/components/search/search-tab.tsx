import { useSearch } from "@/hooks/use-search"
import { useIndexEvents } from "@/hooks/use-index-events"
import { SearchSidebar } from "./search-sidebar"
import { ResultsChangedDialog } from "./results-changed-dialog"
import { SearchHistoryDialog } from "./search-history-dialog"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Markdown } from "@/components/ui/markdown"
import { Loader2, Search, Sparkles, Square, RotateCcw, Clock, AlertCircle, ChevronDown, ChevronRight, History } from "lucide-react"
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
    loading, loadingHistorical, error, search,
    searches, activeSearchId,
    deleteSearch, loadSearch,
    summary, summarySources, isSummarizing, stopSummary, generateSummary,
    newSearch,
    isHistorical,
    resultsChanged,
    missingFiles,
    newFiles,
    scoreChanges,
    storedResultCount,
    currentResultCount,
    createdAt,
    versionCount,
    requery,
    loadVersion,
    fetchVersions,
  } = useSearch()

  const { lastIndexedAt } = useIndexEvents()
  const [viewingPath, setViewingPath] = useState<string | null>(null)
  const [resultsChangedDialogOpen, setResultsChangedDialogOpen] = useState(false)
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false)
  const [confirmGenerateSummaryOpen, setConfirmGenerateSummaryOpen] = useState(false)
  const [expandedResults, setExpandedResults] = useState<Set<number>>(new Set())

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") search()
  }

  function handleConfirmGenerateSummary() {
    setConfirmGenerateSummaryOpen(false)
    generateSummary()
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

                  {/* Staleness indicator */}
                  {createdAt && lastIndexedAt && lastIndexedAt > new Date(createdAt).getTime() / 1000 && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Badge variant="outline" className="text-xs text-warning border-warning/50 cursor-help">
                          <AlertCircle className="h-3 w-3 mr-1" />
                          Sources updated
                        </Badge>
                      </TooltipTrigger>
                      <TooltipContent>
                        Documents were re-indexed after this search. Re-query for fresh results.
                      </TooltipContent>
                    </Tooltip>
                  )}

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

                  {/* History and Re-query buttons (only for historical searches) */}
                  {isHistorical && (
                    <div className="flex items-center gap-2 ml-auto">
                      {versionCount > 1 && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-7 px-2"
                              onClick={() => setHistoryDialogOpen(true)}
                              disabled={loading}
                            >
                              <History className="h-3.5 w-3.5 mr-1" />
                              History ({versionCount})
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs">
                            View all versions of this search
                          </TooltipContent>
                        </Tooltip>
                      )}

                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7 px-2"
                            onClick={requery}
                            disabled={loading}
                          >
                            <RotateCcw className="h-3.5 w-3.5 mr-1" />
                            Re-query
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          Run this query again with current KB state (creates a new version)
                        </TooltipContent>
                      </Tooltip>
                    </div>
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
                          <button
                            onClick={() => setResultsChangedDialogOpen(true)}
                            className="flex items-center gap-2 hover:underline cursor-pointer"
                          >
                            <AlertCircle className="h-3 w-3 text-amber-500" />
                            <span className="text-amber-600 dark:text-amber-400">
                              Results changed
                            </span>
                            {storedResultCount !== undefined && currentResultCount !== undefined && (
                              <Badge variant="outline" className="text-xs">
                                {storedResultCount} → {currentResultCount}
                              </Badge>
                            )}
                          </button>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          <p>Click to view detailed changes</p>
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
                  {loadingHistorical ? "Loading previous search..." : "Searching your knowledge base..."}
                </p>
              </div>
            )}

            {error && (
              <p className="text-destructive text-center py-8">
                Search error: {error}
              </p>
            )}

            {/* AI Summary Card */}
            {(summary || isSummarizing || (isHistorical && !summary)) && (
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
                    {/* Show Generate/Regenerate button for historical searches */}
                    {isHistorical && !isSummarizing && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-6 px-2 ml-auto"
                        onClick={() => setConfirmGenerateSummaryOpen(true)}
                      >
                        <Sparkles className="h-3 w-3 mr-1" />
                        {summary ? "Regenerate" : "Generate Summary"}
                      </Button>
                    )}
                  </div>
                  {!summary && !isSummarizing ? (
                    <p className="text-sm text-muted-foreground italic">
                      No AI summary available for this historical search.
                    </p>
                  ) : (
                    <>
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
                    </>
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
            {results.map((r, i) => {
              const hasMultipleSnippets = (r.snippets?.length ?? 0) > 1
              const isExpanded = expandedResults.has(i)
              const toggleExpanded = (e: React.MouseEvent) => {
                e.stopPropagation()
                setExpandedResults((prev) => {
                  const next = new Set(prev)
                  if (next.has(i)) {
                    next.delete(i)
                  } else {
                    next.add(i)
                  }
                  return next
                })
              }

              return (
                <Card
                  key={`${r.metadata.source_path ?? ""}:${r.score}:${i}`}
                  className="cursor-pointer hover:bg-accent/50 transition-colors"
                  onClick={() => setViewingPath(r.metadata.source_path ?? null)}
                >
                  <CardContent className="pt-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="secondary">
                        {Math.round(r.score * 100)}%
                      </Badge>
                      {r.chunk_count && r.chunk_count > 1 && (
                        <Badge variant="outline" className="text-xs">
                          {r.chunk_count} sections
                        </Badge>
                      )}
                      <span className="text-sm font-mono text-muted-foreground truncate flex-1">
                        {r.metadata.source_path ?? "unknown"}
                      </span>
                      {hasMultipleSnippets && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 shrink-0"
                          onClick={toggleExpanded}
                        >
                          {isExpanded ? (
                            <>
                              <ChevronDown className="h-3 w-3 mr-1" />
                              Hide sections
                            </>
                          ) : (
                            <>
                              <ChevronRight className="h-3 w-3 mr-1" />
                              Show all sections
                            </>
                          )}
                        </Button>
                      )}
                    </div>

                    {/* Show snippets if expanded, otherwise show primary chunk */}
                    {hasMultipleSnippets && isExpanded ? (
                      <div className="space-y-3 mt-3">
                        {r.snippets!.map((snippet, si) => (
                          <div key={si} className="border-l-2 border-primary/30 pl-3">
                            {snippet.heading && (
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-semibold text-primary">
                                  {snippet.heading}
                                </span>
                                <Badge variant="outline" className="text-xs">
                                  {Math.round(snippet.score * 100)}%
                                </Badge>
                              </div>
                            )}
                            <Markdown className="text-sm">
                              {snippet.text.length > 400 ? snippet.text.slice(0, 400) + "..." : snippet.text}
                            </Markdown>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <Markdown className="text-sm">
                        {r.document.length > 500 ? r.document.slice(0, 500) + "..." : r.document}
                      </Markdown>
                    )}
                  </CardContent>
                </Card>
              )
            })}
            </div>
          </ScrollArea>
        )}
      </div>

      <FileViewerDialog
        path={viewingPath}
        onClose={() => setViewingPath(null)}
      />

      <ResultsChangedDialog
        open={resultsChangedDialogOpen}
        onOpenChange={setResultsChangedDialogOpen}
        missingFiles={missingFiles}
        newFiles={newFiles}
        scoreChanges={scoreChanges}
        storedResultCount={storedResultCount || 0}
        currentResultCount={currentResultCount || 0}
      />

      <SearchHistoryDialog
        open={historyDialogOpen}
        onOpenChange={setHistoryDialogOpen}
        activeSearchId={activeSearchId}
        fetchVersions={fetchVersions}
        onSelectVersion={loadVersion}
      />

      <ConfirmDialog
        open={confirmGenerateSummaryOpen}
        onOpenChange={setConfirmGenerateSummaryOpen}
        title={summary ? "Regenerate AI Summary?" : "Generate AI Summary?"}
        description={
          summary
            ? "This will create a new AI summary based on current results. This may take a moment."
            : "This will generate an AI summary of the search results. This may take a moment."
        }
        confirmLabel={summary ? "Regenerate" : "Generate"}
        onConfirm={handleConfirmGenerateSummary}
      />
    </div>
  )
}
