import { useEffect, useState } from "react"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog"
import { Label } from "@/components/ui/label"
import { BookOpen, Loader2, ExternalLink } from "lucide-react"
import { api } from "@/lib/api"
import { toast } from "sonner"

interface IngestResult {
  status: string
  source_path: string
  target_source: string
  pages_written: string[]
  summary_preview: string
  summary_chars: number
}

/**
 * Compile-to-wiki dialog. Takes a source file path, lists writable
 * target sources, runs the wiki_compile ingest, and displays the
 * result. Mirrors the POST /api/wiki-compile/ingest contract.
 */
export function WikiCompileDialog({
  open,
  sourcePath,
  onClose,
}: {
  open: boolean
  sourcePath: string | null
  onClose: () => void
}) {
  const [targets, setTargets] = useState<string[] | null>(null)
  const [targetsError, setTargetsError] = useState<string | null>(null)
  const [selectedTarget, setSelectedTarget] = useState<string>("")
  const [force, setForce] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<IngestResult | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Reset dialog state whenever it opens for a new source.
  useEffect(() => {
    if (!open) return
    setResult(null)
    setSubmitError(null)
    setForce(false)
    setTargets(null)
    setTargetsError(null)
    setSelectedTarget("")
    api.get<{ targets: string[] }>("/api/wiki-compile/targets")
      .then((r) => {
        setTargets(r.targets)
        if (r.targets.length > 0) setSelectedTarget(r.targets[0])
      })
      .catch((err) => setTargetsError((err as Error).message))
  }, [open])

  const handleSubmit = async () => {
    if (!sourcePath || !selectedTarget) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const r = await api.post<IngestResult>("/api/wiki-compile/ingest", {
        source_path: sourcePath,
        target_source: selectedTarget,
        force,
      })
      setResult(r)
      toast.success(`Compiled into ${r.pages_written.length} pages`)
    } catch (err) {
      setSubmitError((err as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = () => {
    if (submitting) return
    onClose()
  }

  const sourceName = sourcePath?.split("/").pop() ?? ""

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) handleClose() }}>
      <AlertDialogContent className="!max-w-lg">
        <AlertDialogTitle className="flex items-center gap-2">
          <BookOpen className="h-4 w-4" />
          Compile into wiki
        </AlertDialogTitle>
        <AlertDialogDescription className="text-xs">
          Reads <span className="font-mono">{sourceName}</span>, asks the configured LLM to synthesize a summary page, and writes it into a writable source directory. Updates <span className="font-mono">index.md</span> and appends <span className="font-mono">log.md</span>.
        </AlertDialogDescription>

        {/* Target selection — only shown pre-submit */}
        {!result && (
          <div className="space-y-3 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs">Target writable source</Label>
              {targetsError ? (
                <p className="text-xs text-destructive">
                  Could not load targets: {targetsError}
                </p>
              ) : targets === null ? (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Loading...
                </div>
              ) : targets.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No writable sources configured. Add one with <span className="font-mono">writable: true</span> in <span className="font-mono">config/settings.yaml</span>.
                </p>
              ) : (
                <select
                  value={selectedTarget}
                  onChange={(e) => setSelectedTarget(e.target.value)}
                  className="w-full text-xs border rounded px-2 py-1.5 bg-background"
                  disabled={submitting}
                >
                  {targets.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              )}
            </div>

            <label className="flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={force}
                onChange={(e) => setForce(e.target.checked)}
                disabled={submitting}
              />
              Overwrite if a summary already exists for this source
            </label>

            {submitError && (
              <p className="text-xs text-destructive break-words">{submitError}</p>
            )}
          </div>
        )}

        {/* Result view — shown post-submit */}
        {result && (
          <div className="space-y-3 py-2">
            <div className="rounded border bg-muted/40 px-3 py-2 space-y-1.5 text-xs">
              <p className="font-medium">Wrote {result.pages_written.length} pages into:</p>
              <p className="font-mono text-muted-foreground break-all">{result.target_source}</p>
              <ul className="space-y-0.5 pl-3">
                {result.pages_written.map((p) => (
                  <li key={p} className="font-mono">· {p}</li>
                ))}
              </ul>
            </div>
            <div className="rounded border border-primary/20 bg-primary/5 px-3 py-2">
              <p className="text-[11px] font-medium text-primary mb-1 flex items-center gap-1">
                <ExternalLink className="h-3 w-3" />
                Summary preview ({result.summary_chars} chars)
              </p>
              <p className="text-xs leading-relaxed whitespace-pre-wrap break-words">
                {result.summary_preview}
                {result.summary_chars > result.summary_preview.length ? "…" : ""}
              </p>
            </div>
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel onClick={handleClose} disabled={submitting}>
            {result ? "Close" : "Cancel"}
          </AlertDialogCancel>
          {!result && (
            <AlertDialogAction
              onClick={handleSubmit}
              disabled={submitting || !selectedTarget || targets === null || (targets?.length ?? 0) === 0}
            >
              {submitting ? (
                <><Loader2 className="h-3 w-3 animate-spin mr-1.5" /> Compiling…</>
              ) : (
                "Compile"
              )}
            </AlertDialogAction>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
