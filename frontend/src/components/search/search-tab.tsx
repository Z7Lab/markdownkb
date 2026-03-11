import { useSearch } from "@/hooks/use-search"
import { useScopes } from "@/hooks/use-scopes"
import { useTags } from "@/hooks/use-tags"
import { useSettings } from "@/hooks/use-settings"
import { useIndexEvents } from "@/hooks/use-index-events"
import { SearchSidebar } from "./search-sidebar"
import { SearchSummaryCard } from "./search-summary-card"
import { SearchResultCard } from "./search-result-card"
import { ResultsChangedDialog } from "./results-changed-dialog"
import { SearchHistoryDialog } from "./search-history-dialog"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { DeepResearchToggle } from "@/components/ui/deep-research-toggle"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Loader2, Search, RotateCcw, Clock, AlertCircle, History } from "lucide-react"
import { useMemo, useState, type KeyboardEvent } from "react"
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
  const { scopes } = useScopes()
  const { tags: availableTags } = useTags()
  const { settings } = useSettings()

  const [selectedScopeIds, setSelectedScopeIds] = useState<Set<string>>(new Set())
  const [selectedAdHocTags, setSelectedAdHocTags] = useState<Set<string>>(new Set())

  const scopeIdsParam = useMemo(() => {
    if (selectedScopeIds.size === 0) return null
    return Array.from(selectedScopeIds).join(",")
  }, [selectedScopeIds])

  const adHocTagsParam = useMemo(() => {
    if (selectedAdHocTags.size === 0) return null
    return Array.from(selectedAdHocTags)
  }, [selectedAdHocTags])

  const {
    query, setQuery,
    folder, setFolder,
    tag, setTag,
    results, folders, tags,
    loading, loadingHistorical, error, search,
    searches, activeSearchId,
    deleteSearch, loadSearch,
    summary, summarySources, summaryStatus, isSummarizing, stopSummary, generateSummary,
    deepResearch, setDeepResearch,
    deepResearchIterations, setDeepResearchIterations,
    summaryIteration, summaryTotalIterations,
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
  } = useSearch(scopeIdsParam, adHocTagsParam)
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
        scopes={scopes}
        selectedFolder={folder}
        selectedTag={tag}
        selectedScopeIds={selectedScopeIds}
        onNewSearch={newSearch}
        onLoadSearch={loadSearch}
        onDeleteSearch={deleteSearch}
        onFolderChange={setFolder}
        onTagChange={setTag}
        onScopeChange={setSelectedScopeIds}
        availableTags={availableTags}
        selectedAdHocTags={selectedAdHocTags}
        onAdHocTagChange={setSelectedAdHocTags}
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
            <div className="flex gap-2 w-full max-w-2xl items-center">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search your knowledge base..."
                className="flex-1"
              />
              <DeepResearchToggle
                enabled={deepResearch}
                onToggle={setDeepResearch}
                featureEnabled={settings?.features?.deep_research ?? false}
                disabled={loading}
                iterations={deepResearchIterations}
                onIterationsChange={setDeepResearchIterations}
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

                  {/* Deep research toggle */}
                  {!isHistorical && (
                    <div className="ml-auto">
                      <DeepResearchToggle
                        enabled={deepResearch}
                        onToggle={setDeepResearch}
                        featureEnabled={settings?.features?.deep_research ?? false}
                        disabled={isSummarizing}
                        iterations={deepResearchIterations}
                        onIterationsChange={setDeepResearchIterations}
                      />
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
              <SearchSummaryCard
                summary={summary}
                summarySources={summarySources}
                isSummarizing={isSummarizing}
                isHistorical={isHistorical}
                statusMessage={summaryStatus}
                isDeepResearch={deepResearch}
                iteration={summaryIteration}
                totalIterations={summaryTotalIterations}
                onStop={stopSummary}
                onGenerate={() => setConfirmGenerateSummaryOpen(true)}
                onSelectSource={setViewingPath}
              />
            )}

            {/* Empty state - only show after search with no results */}
            {results.length === 0 && !loading && !error && !summary && query && (
              <p className="text-muted-foreground text-center py-8">
                No results found for "{query}"
              </p>
            )}
            {results.map((r, i) => (
              <SearchResultCard
                key={`${r.metadata.source_path ?? ""}:${r.score}:${i}`}
                result={r}
                isExpanded={expandedResults.has(i)}
                onToggleExpanded={(e) => {
                  e.stopPropagation()
                  setExpandedResults((prev) => {
                    const next = new Set(prev)
                    if (next.has(i)) next.delete(i)
                    else next.add(i)
                    return next
                  })
                }}
                onSelect={(path) => setViewingPath(path || null)}
              />
            ))}
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
