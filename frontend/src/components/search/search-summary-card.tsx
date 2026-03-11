import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Markdown } from "@/components/ui/markdown"
import { SourceList } from "@/components/ui/source-badge"
import { Progress } from "@/components/ui/progress"
import { Loader2, Microscope, Sparkles, Square } from "lucide-react"

export function SearchSummaryCard({
  summary,
  summarySources,
  isSummarizing,
  isHistorical,
  statusMessage,
  isDeepResearch,
  iteration,
  totalIterations,
  onStop,
  onGenerate,
  onSelectSource,
}: {
  summary: string | null
  summarySources: string[]
  isSummarizing: boolean
  isHistorical: boolean
  statusMessage?: string | null
  isDeepResearch?: boolean
  iteration?: number
  totalIterations?: number
  onStop: () => void
  onGenerate: () => void
  onSelectSource: (path: string) => void
}) {
  const label = isDeepResearch ? "Deep Research" : "AI Summary"
  const Icon = isDeepResearch ? Microscope : Sparkles

  // Progress calculation for deep research: iterations are the main work,
  // then synthesis is the final stretch
  const showProgress = isDeepResearch && isSummarizing && totalIterations && totalIterations > 0
  let progressValue = 0
  if (showProgress) {
    // Reserve 80% for iterations, 20% for synthesis
    const iterPortion = Math.min((iteration ?? 0) / totalIterations, 1) * 80
    // If we're past all iterations (synthesizing), fill toward 100
    const isSynthesizing = (iteration ?? 0) >= totalIterations && statusMessage?.includes("Synthesiz")
    progressValue = isSynthesizing ? 85 : iterPortion
  }

  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardContent className="pt-4">
        <div className="flex items-center gap-2 mb-3">
          <Icon className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-primary">{label}</span>
          {isSummarizing && (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
              {statusMessage && (
                <span className="text-xs text-muted-foreground">{statusMessage}</span>
              )}
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5 ml-auto"
                onClick={onStop}
                aria-label="Stop summary"
              >
                <Square className="h-3 w-3" />
              </Button>
            </>
          )}
          {isHistorical && !isSummarizing && (
            <Button
              variant="outline"
              size="sm"
              className="h-6 px-2 ml-auto"
              onClick={onGenerate}
            >
              <Sparkles className="h-3 w-3 mr-1" />
              {summary ? "Regenerate" : "Generate Summary"}
            </Button>
          )}
        </div>
        {showProgress && (
          <Progress value={progressValue} className="h-1.5 mb-3" />
        )}
        {!summary && !isSummarizing ? (
          <p className="text-sm text-muted-foreground italic">
            No AI summary available for this historical search.
          </p>
        ) : (
          <>
            <Markdown className="text-sm">{summary || "Generating summary..."}</Markdown>
            {summarySources.length > 0 && (
              <SourceList
                sources={summarySources}
                onSelect={onSelectSource}
                className="flex flex-wrap items-center gap-1.5 mt-3 pt-3 border-t"
              />
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
