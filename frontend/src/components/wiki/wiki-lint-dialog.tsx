import { useState } from "react"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Markdown } from "@/components/ui/markdown"
import { ClipboardCheck, Loader2, AlertCircle, AlertTriangle, Info, FileText } from "lucide-react"
import { api } from "@/lib/api"
import { toast } from "sonner"

type PassName = "raw_coverage" | "orphan" | "within_tier" | "cross_tier"

interface Finding {
  pass: PassName
  severity: "critical" | "warning" | "info"
  kind: string
  title: string
  detail: string
  paths: string[]
  suggested_action: string
}

interface RunResponse {
  findings: Finding[]
  counts: Record<"critical" | "warning" | "info", number>
  report_path: string
  report_markdown: string
  passes_run: PassName[]
}

const PASS_META: Record<PassName, { label: string; description: string; llm: boolean }> = {
  raw_coverage: { label: "Raw coverage", description: "Raw (tier -1) files that no wiki has synthesized yet.", llm: false },
  orphan: { label: "Orphans", description: "Tier-1 docs no other doc links to.", llm: false },
  within_tier: { label: "Within-tier contradictions", description: "LLM-flagged opposing claims between two derived docs.", llm: true },
  cross_tier: { label: "Cross-tier tensions", description: "LLM classification of derived doc vs canonical: extension, contradiction, evolution.", llm: true },
}

/**
 * Runs the wiki_lint passes and shows a findings summary + rendered
 * report. Findings can be expanded inline; the full markdown report
 * can be opened in the file viewer.
 */
export function WikiLintDialog({
  open, onClose, targetWiki, onOpenReport,
}: {
  open: boolean
  onClose: () => void
  targetWiki: string
  onOpenReport?: (path: string) => void
}) {
  const [selectedPasses, setSelectedPasses] = useState<Set<PassName>>(
    new Set(["raw_coverage", "orphan"] as PassName[]),
  )
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<RunResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const togglePass = (p: PassName) => {
    const next = new Set(selectedPasses)
    if (next.has(p)) next.delete(p)
    else next.add(p)
    setSelectedPasses(next)
  }

  const runLint = async () => {
    setRunning(true)
    setError(null)
    try {
      const r = await api.post<RunResponse>("/api/v1/lint/run", {
        passes: Array.from(selectedPasses),
        target_wiki: targetWiki,
      })
      setResult(r)
      toast.success(`Lint complete — ${r.findings.length} finding${r.findings.length === 1 ? "" : "s"}`)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setRunning(false)
    }
  }

  const severityIcon = (s: "critical" | "warning" | "info") => {
    if (s === "critical") return <AlertCircle className="h-3.5 w-3.5 text-destructive" />
    if (s === "warning") return <AlertTriangle className="h-3.5 w-3.5 text-yellow-500" />
    return <Info className="h-3.5 w-3.5 text-muted-foreground" />
  }

  const hasLlmSelected = Array.from(selectedPasses).some((p) => PASS_META[p].llm)

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o && !running) onClose() }}>
      <AlertDialogContent className="!max-w-3xl !max-h-[85vh] flex flex-col">
        <AlertDialogTitle className="flex items-center gap-2">
          <ClipboardCheck className="h-4 w-4" />
          Wiki lint — <span className="font-mono text-xs">{targetWiki}</span>
        </AlertDialogTitle>
        <AlertDialogDescription className="text-xs">
          Tiered health check over your configured sources. LLM passes are bounded (up to 12 doc pairs each) and err toward ALIGNED to avoid false contradiction flags. Findings only — nothing is modified.
        </AlertDialogDescription>

        {!result ? (
          <div className="space-y-3 py-2 flex-1 min-h-0 overflow-auto">
            <div className="space-y-1.5">
              <p className="text-xs font-medium">Passes to run</p>
              {(Object.keys(PASS_META) as PassName[]).map((p) => (
                <label key={p} className="flex items-start gap-2 text-xs cursor-pointer rounded hover:bg-accent px-2 py-1.5">
                  <input
                    type="checkbox"
                    checked={selectedPasses.has(p)}
                    onChange={() => togglePass(p)}
                    disabled={running}
                    className="mt-0.5"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{PASS_META[p].label}</span>
                      {PASS_META[p].llm && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary">LLM</span>
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground">{PASS_META[p].description}</p>
                  </div>
                </label>
              ))}
            </div>

            {hasLlmSelected && (
              <p className="text-[11px] text-muted-foreground italic border rounded px-2 py-1.5">
                LLM passes require an active model provider and may take 30s–3min depending on corpus size.
              </p>
            )}

            {error && <p className="text-xs text-destructive break-words">{error}</p>}
          </div>
        ) : (
          <div className="flex-1 min-h-0 flex flex-col gap-3 py-2">
            <div className="flex items-center gap-4 text-xs">
              <span className="flex items-center gap-1">
                <AlertCircle className="h-3 w-3 text-destructive" />
                {result.counts.critical} critical
              </span>
              <span className="flex items-center gap-1">
                <AlertTriangle className="h-3 w-3 text-yellow-500" />
                {result.counts.warning} warning
              </span>
              <span className="flex items-center gap-1">
                <Info className="h-3 w-3 text-muted-foreground" />
                {result.counts.info} info
              </span>
              <span className="flex-1" />
              <Button
                variant="outline"
                size="sm"
                className="h-6 text-xs gap-1"
                onClick={() => onOpenReport?.(result.report_path)}
              >
                <FileText className="h-3 w-3" />
                Open report
              </Button>
            </div>

            <ScrollArea className="flex-1 min-h-0 border rounded-md">
              {result.findings.length === 0 ? (
                <div className="p-6 text-center text-sm text-muted-foreground italic">
                  No findings. The wiki is consistent under the rules these passes apply.
                </div>
              ) : (
                <div className="p-4 space-y-3">
                  {result.findings.map((f, i) => (
                    <details key={i} className="rounded border px-3 py-2 text-xs group">
                      <summary className="cursor-pointer flex items-start gap-2">
                        {severityIcon(f.severity)}
                        <span className="font-medium flex-1">{f.title}</span>
                        <span className="text-[10px] text-muted-foreground px-1.5 py-0.5 rounded bg-muted">
                          {PASS_META[f.pass]?.label ?? f.pass}
                        </span>
                      </summary>
                      <div className="mt-2 pl-5 space-y-2 text-muted-foreground">
                        <Markdown>{f.detail}</Markdown>
                        {f.suggested_action && (
                          <p><span className="font-medium text-foreground">Suggested:</span> {f.suggested_action}</p>
                        )}
                        {f.paths.length > 0 && (
                          <ul className="space-y-0.5">
                            {f.paths.slice(0, 25).map((p) => (
                              <li key={p} className="font-mono text-[11px] break-all">
                                <button
                                  className="hover:underline text-left"
                                  onClick={(e) => { e.preventDefault(); onOpenReport?.(p) }}
                                >
                                  {p}
                                </button>
                              </li>
                            ))}
                            {f.paths.length > 25 && (
                              <li className="italic">…and {f.paths.length - 25} more</li>
                            )}
                          </ul>
                        )}
                      </div>
                    </details>
                  ))}
                </div>
              )}
            </ScrollArea>
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel disabled={running}>Close</AlertDialogCancel>
          {!result && (
            <Button
              onClick={runLint}
              disabled={running || selectedPasses.size === 0}
            >
              {running ? <><Loader2 className="h-3 w-3 animate-spin mr-1.5" /> Running…</> : "Run lint"}
            </Button>
          )}
          {result && (
            <Button variant="outline" onClick={() => setResult(null)}>
              Run again
            </Button>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
