import { usePlanner } from "@/hooks/use-planner"
import { useScopes } from "@/hooks/use-scopes"
import { useTags } from "@/hooks/use-tags"
import { useScopeTagFilter } from "@/hooks/use-scope-tag-filter"
import { useBuckets } from "@/hooks/use-buckets"
import { PlannerSidebar } from "./planner-sidebar"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Markdown } from "@/components/ui/markdown"
import { SourceList } from "@/components/ui/source-badge"
import { PlannerSkillReview } from "./planner-skill-review"
import { Loader2, Lightbulb, Square, Save, Download } from "lucide-react"
import { useEffect, useRef, useState, type KeyboardEvent } from "react"
import { EmptyHero } from "@/components/ui/empty-hero"

export function PlannerTab() {
  const {
    plan, sources, approaches, reviews, refinedPlan, query,
    statusMessage, isPlanning, isRefined,
    savedPlans, activePlanId,
    generatePlan, stop, clear, savePlan, loadPlan, renamePlan, deletePlan,
  } = usePlanner()

  const { scopes } = useScopes()
  const { tags: availableTags } = useTags()
  const { buckets } = useBuckets()
  const {
    selectedScopeIds, selectedTags,
    scopeIdsParam, adHocTagsParam,
    selectedBucketId,
    handleScopeChange, handleTagChange,
    handleBucketChange,
  } = useScopeTagFilter()

  const [inputQuery, setInputQuery] = useState("")
  const [viewingPath, setViewingPath] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (isPlanning) {
      setElapsed(0)
      timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
      timerRef.current = null
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [isPlanning])

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") handleGenerate()
  }

  function handleGenerate() {
    if (!inputQuery.trim() || isPlanning) return
    generatePlan(inputQuery, { scope_ids: scopeIdsParam, ad_hoc_tags: adHocTagsParam, bucket_id: selectedBucketId })
  }

  function handleNewPlan() {
    clear()
    setInputQuery("")
  }

  function handleDownload() {
    const content = isRefined && refinedPlan ? refinedPlan : plan
    if (!content) return
    const blob = new Blob([content], { type: "text/markdown" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `plan-${query.slice(0, 40).replace(/[^a-zA-Z0-9]+/g, "-")}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const hasResults = plan || approaches.length > 0

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <PlannerSidebar
        plans={savedPlans}
        activePlanId={activePlanId}
        scopes={scopes}
        selectedScopeIds={selectedScopeIds}
        onScopeChange={handleScopeChange}
        availableTags={availableTags}
        selectedTags={selectedTags}
        onTagChange={handleTagChange}
        buckets={buckets}
        selectedBucketId={selectedBucketId}
        onBucketChange={handleBucketChange}
        onNewPlan={handleNewPlan}
        onLoadPlan={loadPlan}
        onRenamePlan={renamePlan}
        onDeletePlan={deletePlan}
      />

      <div className="flex flex-col flex-1 min-w-0 min-h-0 h-full">
        {/* Empty state */}
        {!hasResults && !isPlanning && (
          <div className="flex flex-col items-center justify-start flex-1 gap-6 p-4 pt-[20vh]">
            <EmptyHero icon={Lightbulb} label="Planner" />

            <div className="flex gap-2 w-full max-w-2xl">
              <Input
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe what you want to build..."
                className="flex-1"
              />
              <Button onClick={handleGenerate} disabled={isPlanning || !inputQuery.trim()}>
                <Lightbulb className="h-4 w-4 mr-1.5" />
                Generate Plan
              </Button>
            </div>
          </div>
        )}

        {/* Results / planning state */}
        {(hasResults || isPlanning) && (
          <ScrollArea className="flex-1 min-h-0">
            <div className="space-y-3 p-4 pb-4">
              {/* Query header */}
              {query && (
                <div className="flex items-center gap-2 pb-2 border-b">
                  <Lightbulb className="h-4 w-4 text-muted-foreground" />
                  <h2 className="text-base font-semibold text-foreground">{query}</h2>
                  <div className="ml-auto flex items-center gap-2">
                    {isPlanning && (
                      <Button variant="outline" size="sm" className="h-7 px-2" onClick={stop}>
                        <Square className="h-3.5 w-3.5 mr-1" />
                        Stop
                      </Button>
                    )}
                    {!isPlanning && plan && (
                      <>
                        <Button variant="outline" size="sm" className="h-7 px-2" onClick={savePlan}>
                          <Save className="h-3.5 w-3.5 mr-1" />
                          Save
                        </Button>
                        <Button variant="outline" size="sm" className="h-7 px-2" onClick={handleDownload}>
                          <Download className="h-3.5 w-3.5 mr-1" />
                          Download
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* Status indicator */}
              {isPlanning && statusMessage && (
                <div className="flex items-center gap-3 py-4 justify-center">
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                  <p className="text-sm text-muted-foreground">{statusMessage}</p>
                  <span className="text-xs text-muted-foreground/60 tabular-nums">
                    {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
                  </span>
                </div>
              )}

              {/* Plan — shown above approaches */}
              {plan && (
                <Card className="border-primary/30 bg-primary/5">
                  <CardContent className="pt-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Lightbulb className="h-4 w-4 text-primary" />
                      <span className="text-sm font-semibold text-primary">
                        {isRefined ? "Refined Plan" : "Implementation Plan"}
                      </span>
                    </div>
                    <Markdown className="text-sm">{isRefined && refinedPlan ? refinedPlan : plan}</Markdown>
                  </CardContent>
                </Card>
              )}

              {/* Sources */}
              {sources.length > 0 && (
                <SourceList
                  sources={sources}
                  onSelect={setViewingPath}
                  label={false}
                  className="flex flex-wrap gap-1.5"
                />
              )}

              {/* Skill reviews */}
              <PlannerSkillReview reviews={reviews} />

              {/* Explored approaches — shown below plan */}
              {approaches.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Explored Approaches</h3>
                  <div className="grid gap-2">
                    {approaches.map((a, i) => (
                      <Card key={i} className="bg-muted/30">
                        <CardContent className="pt-3 pb-3">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant="secondary">{Math.round(a.score * 100)}%</Badge>
                            <span className="text-xs text-muted-foreground">Approach {i + 1}</span>
                          </div>
                          <Markdown className="text-sm">
                            {a.content.length > 500 ? a.content.slice(0, 500) + "..." : a.content}
                          </Markdown>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        )}

        <FileViewerDialog
          path={viewingPath}
          onClose={() => setViewingPath(null)}
        />
      </div>
    </div>
  )
}
