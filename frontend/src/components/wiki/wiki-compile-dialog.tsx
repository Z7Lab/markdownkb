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
  wiki?: string
  existing_pages_used?: string[]
}

interface WikiRecord {
  id: string
  name: string
  path: string
  page_count: number
  last_ingest_at: string | null
  created_at: string
}

interface CreateWikiResponse extends WikiRecord {
  docker_restart_required: boolean
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
  defaultWiki,
  pickSourcePath = false,
}: {
  open: boolean
  sourcePath: string | null
  onClose: () => void
  /** When set, pre-selects this wiki in the dropdown. */
  defaultWiki?: string
  /** When true, renders a source-path input instead of assuming sourcePath is fixed. */
  pickSourcePath?: boolean
}) {
  const [wikis, setWikis] = useState<WikiRecord[] | null>(null)
  const [wikisError, setWikisError] = useState<string | null>(null)
  const [selectedWiki, setSelectedWiki] = useState<string>("")
  const [force, setForce] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<IngestResult | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [manualSourcePath, setManualSourcePath] = useState<string>("")

  // Inline-create state for when no wikis exist yet.
  const [newWikiName, setNewWikiName] = useState("")
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const effectiveSourcePath = pickSourcePath ? manualSourcePath.trim() : sourcePath

  const loadWikis = () => {
    setWikis(null)
    setWikisError(null)
    api.get<{ wikis: WikiRecord[] }>("/api/v1/wiki-compile/wikis")
      .then((r) => {
        setWikis(r.wikis)
        const preferred = defaultWiki && r.wikis.some((w) => w.name === defaultWiki)
          ? defaultWiki
          : r.wikis[0]?.name ?? ""
        setSelectedWiki(preferred)
      })
      .catch((err) => setWikisError((err as Error).message))
  }

  // Reset dialog state whenever it opens for a new source.
  useEffect(() => {
    if (!open) return
    setResult(null)
    setSubmitError(null)
    setCreateError(null)
    setForce(false)
    setNewWikiName("")
    setManualSourcePath("")
    loadWikis()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, defaultWiki])

  const handleSubmit = async () => {
    if (!effectiveSourcePath || !selectedWiki) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const r = await api.post<IngestResult>("/api/v1/wiki-compile/ingest", {
        source_path: effectiveSourcePath,
        wiki: selectedWiki,
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

  const handleCreateWiki = async () => {
    const name = newWikiName.trim()
    if (!name) return
    setCreating(true)
    setCreateError(null)
    try {
      const r = await api.post<CreateWikiResponse>("/api/v1/wiki-compile/wikis", { name })
      if (r.docker_restart_required) {
        toast.warning("Wiki created — Docker restart required to mount the path before ingest.")
      } else {
        toast.success(`Wiki "${r.name}" created.`)
      }
      setNewWikiName("")
      // Refresh the list and pre-select the new wiki.
      const list = await api.get<{ wikis: WikiRecord[] }>("/api/v1/wiki-compile/wikis")
      setWikis(list.wikis)
      setSelectedWiki(r.name)
    } catch (err) {
      setCreateError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  const handleClose = () => {
    if (submitting) return
    onClose()
  }

  const sourceName = effectiveSourcePath?.split("/").pop() ?? ""

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) handleClose() }}>
      <AlertDialogContent className="!max-w-lg">
        <AlertDialogTitle className="flex items-center gap-2">
          <BookOpen className="h-4 w-4" />
          Compile into wiki
        </AlertDialogTitle>
        <AlertDialogDescription className="text-xs">
          {pickSourcePath
            ? <>Enter an absolute path to a markdown file; mdkb reads it, asks the configured LLM to synthesize a summary page, and writes it into the target wiki.</>
            : <>Reads <span className="font-mono">{sourceName}</span>, asks the configured LLM to synthesize a summary page, and writes it into a writable source directory. Updates <span className="font-mono">index.md</span> and appends <span className="font-mono">log.md</span>.</>
          }
        </AlertDialogDescription>

        {/* Wiki selection — only shown pre-submit */}
        {!result && (
          <div className="space-y-3 py-2">
            {pickSourcePath && (
              <div className="space-y-1.5">
                <Label className="text-xs">Source file path</Label>
                <input
                  type="text"
                  value={manualSourcePath}
                  onChange={(e) => setManualSourcePath(e.target.value)}
                  placeholder="/absolute/path/to/source.md"
                  className="w-full text-xs border rounded px-2 py-1.5 bg-background font-mono"
                  disabled={submitting}
                />
              </div>
            )}
            <div className="space-y-1.5">
              <Label className="text-xs">Target wiki</Label>
              {wikisError ? (
                <p className="text-xs text-destructive">
                  Could not load wikis: {wikisError}
                </p>
              ) : wikis === null ? (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Loading...
                </div>
              ) : wikis.length === 0 ? (
                <div className="space-y-2 rounded border border-dashed px-3 py-2.5">
                  <p className="text-xs text-muted-foreground">
                    No wikis yet. Create one to compile into:
                  </p>
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      value={newWikiName}
                      onChange={(e) => setNewWikiName(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter" && newWikiName.trim()) handleCreateWiki() }}
                      placeholder="research"
                      className="flex-1 text-xs border rounded px-2 py-1 bg-background"
                      disabled={creating}
                      autoFocus
                    />
                    <button
                      onClick={handleCreateWiki}
                      disabled={creating || !newWikiName.trim()}
                      className="text-xs px-2.5 py-1 rounded border border-primary/40 text-primary hover:bg-primary/10 disabled:opacity-50 cursor-pointer disabled:cursor-wait"
                    >
                      {creating ? "…" : "Create"}
                    </button>
                  </div>
                  {createError && (
                    <p className="text-xs text-destructive break-words">{createError}</p>
                  )}
                </div>
              ) : (
                <select
                  value={selectedWiki}
                  onChange={(e) => setSelectedWiki(e.target.value)}
                  className="w-full text-xs border rounded px-2 py-1.5 bg-background"
                  disabled={submitting}
                >
                  {wikis.map((w) => (
                    <option key={w.name} value={w.name}>
                      {w.name} {w.page_count > 0 ? `(${w.page_count} pages)` : ""}
                    </option>
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
              <p className="font-medium">
                Wrote {result.pages_written.length} pages
                {result.wiki && <> into wiki <span className="font-mono">{result.wiki}</span></>}
                :
              </p>
              <p className="font-mono text-muted-foreground break-all">{result.target_source}</p>
              <ul className="space-y-0.5 pl-3">
                {result.pages_written.map((p) => (
                  <li key={p} className="font-mono">· {p}</li>
                ))}
              </ul>
              {result.existing_pages_used && result.existing_pages_used.length > 0 && (
                <p className="text-muted-foreground pt-1">
                  Cross-referenced {result.existing_pages_used.length} existing page
                  {result.existing_pages_used.length === 1 ? "" : "s"} in this wiki
                </p>
              )}
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
              disabled={submitting || !selectedWiki || wikis === null || (wikis?.length ?? 0) === 0 || !effectiveSourcePath}
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
