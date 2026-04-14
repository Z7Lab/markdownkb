import { useEffect, useMemo, useState } from "react"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Loader2, FileUp, X, Plus } from "lucide-react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"

type FrontmatterMode = "none" | "minimal" | "full"

interface WikiRecord {
  id: string
  name: string
  path: string
  page_count: number
}

interface WriteResponse {
  status: string
  path: string
  relative_path: string
  source: string
  version_commit?: string | null
}

export interface PromoteSource {
  path: string
  title?: string
}

/**
 * Files a generated answer (chat message, search summary, or planner
 * output) back into the knowledge base as a new markdown document.
 *
 * The target can be any writable source; when wikis exist, they're
 * pre-selected since that's the common case (Karpathy's 'good answers
 * filed back into the wiki').
 *
 * The dialog is stateless across opens — caller drives content via
 * props; the target, filename, tags, and frontmatter mode are local to
 * each session.
 */
export function PromoteDialog({
  open,
  onClose,
  content,
  suggestedTitle,
  sources,
  kind,
  onPromoted,
}: {
  open: boolean
  onClose: () => void
  /** Markdown content to save. Required. */
  content: string
  /** Optional seed for filename. First heading wins if not supplied. */
  suggestedTitle?: string
  /** Source docs the content was derived from. Rendered as a provenance footer. */
  sources?: PromoteSource[]
  /** Used in frontmatter and as the tag default. */
  kind: "chat" | "search" | "planner" | "custom"
  onPromoted?: (resp: WriteResponse) => void
}) {
  const [wikis, setWikis] = useState<WikiRecord[] | null>(null)
  const [writableSources, setWritableSources] = useState<string[] | null>(null)
  const [target, setTarget] = useState<string>("")
  const [filename, setFilename] = useState("")
  const [fmMode, setFmMode] = useState<FrontmatterMode>("minimal")
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Derive a filename stem from the first markdown heading or from
  // suggestedTitle or from the leading prose.
  const defaultStem = useMemo(() => {
    const heading = content.match(/^\s*#+\s+(.+?)\s*$/m)?.[1]
    const seed = heading ?? suggestedTitle ?? content.split("\n").find((l) => l.trim())?.slice(0, 60) ?? "note"
    return slugify(seed) || "note"
  }, [content, suggestedTitle])

  useEffect(() => {
    if (!open) return
    setSubmitting(false)
    setError(null)
    setTags([kind])
    setTagInput("")
    setFmMode("minimal")
    setFilename(`${defaultStem}.md`)

    // Load wikis + writable sources in parallel.
    Promise.all([
      api.get<{ wikis: WikiRecord[] }>("/api/wiki-compile/wikis").catch(() => ({ wikis: [] })),
      api.get<{ sources: string[] }>("/api/sources"),
      api.get<{ source_configs?: { path: string; writable: boolean }[] }>("/api/settings"),
    ]).then(([wikisResp, , settingsResp]) => {
      const writable = (settingsResp.source_configs ?? [])
        .filter((s) => s.writable)
        .map((s) => s.path)
      setWikis(wikisResp.wikis ?? [])
      setWritableSources(writable)
      // Preferred default: the first wiki path if any, else first writable source.
      const firstWikiPath = wikisResp.wikis?.[0]?.path
      setTarget(firstWikiPath ?? writable[0] ?? "")
    })
  }, [open, defaultStem, kind])

  const addTag = () => {
    const v = tagInput.trim()
    if (v && !tags.includes(v)) {
      setTags([...tags, v])
      setTagInput("")
    }
  }

  const removeTag = (t: string) => setTags(tags.filter((x) => x !== t))

  function buildDocument(): string {
    const parts: string[] = []
    const now = new Date().toISOString()
    if (fmMode === "minimal") {
      parts.push("---")
      parts.push(`date: ${now.slice(0, 10)}`)
      parts.push(`promoted_from: ${kind}`)
      if (tags.length > 0) parts.push(`tags: [${tags.map((t) => JSON.stringify(t)).join(", ")}]`)
      parts.push("---", "")
    } else if (fmMode === "full") {
      parts.push("---")
      parts.push(`date: ${now}`)
      parts.push(`promoted_from: ${kind}`)
      if (tags.length > 0) parts.push(`tags: [${tags.map((t) => JSON.stringify(t)).join(", ")}]`)
      if (sources && sources.length > 0) {
        parts.push("compiled_from:")
        for (const s of sources) parts.push(`  - ${JSON.stringify(s.path)}`)
      }
      parts.push("---", "")
    }
    parts.push(content.trim())
    if (sources && sources.length > 0) {
      parts.push("", "## Compiled from", "")
      for (const s of sources) {
        const label = s.title ?? s.path.split("/").pop() ?? s.path
        parts.push(`- \`${s.path}\` — ${label}`)
      }
    }
    return parts.join("\n") + "\n"
  }

  async function handleSubmit() {
    if (!target || !filename.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const body = {
        path: filename.trim(),
        content: buildDocument(),
        source: target,
        overwrite: false,
      }
      const resp = await api.post<WriteResponse>("/api/documents", body)
      toast.success(`Filed to ${resp.source}`)
      onPromoted?.(resp)
      onClose()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const loading = wikis === null || writableSources === null
  const allTargets: { path: string; label: string; kind: "wiki" | "source" }[] = useMemo(() => {
    const list: { path: string; label: string; kind: "wiki" | "source" }[] = []
    for (const w of wikis ?? []) list.push({ path: w.path, label: `wiki: ${w.name}`, kind: "wiki" })
    const seen = new Set(list.map((x) => x.path))
    for (const s of writableSources ?? []) {
      if (seen.has(s)) continue
      list.push({ path: s, label: s, kind: "source" })
    }
    return list
  }, [wikis, writableSources])

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o && !submitting) onClose() }}>
      <AlertDialogContent className="!max-w-lg">
        <AlertDialogTitle className="flex items-center gap-2">
          <FileUp className="h-4 w-4" />
          File as wiki page
        </AlertDialogTitle>
        <AlertDialogDescription className="text-xs">
          Saves this {kind} output as a markdown file in a writable source. The indexer picks it up next cycle so it becomes searchable and retrievable alongside the rest of your knowledge base.
        </AlertDialogDescription>

        {loading ? (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground py-4">
            <Loader2 className="h-3 w-3 animate-spin" />
            Loading targets...
          </div>
        ) : allTargets.length === 0 ? (
          <p className="text-xs text-destructive py-4">
            No writable sources configured. Add one under Settings → Sources (or create a wiki) and try again.
          </p>
        ) : (
          <div className="space-y-3 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs">Target</Label>
              <select
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                className="w-full text-xs border rounded px-2 py-1.5 bg-background font-mono"
                disabled={submitting}
              >
                {allTargets.map((t) => (
                  <option key={t.path} value={t.path}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Filename</Label>
              <Input
                value={filename}
                onChange={(e) => setFilename(e.target.value)}
                className="h-8 text-xs font-mono"
                disabled={submitting}
                placeholder="note.md"
              />
              <p className="text-[10px] text-muted-foreground">
                Relative path inside <span className="font-mono">{target}</span>. Must end with <span className="font-mono">.md</span>.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Tags</Label>
              <div className="flex flex-wrap gap-1.5 mb-1">
                {tags.map((t) => (
                  <Badge key={t} variant="secondary" className="gap-1 text-[10px]">
                    {t}
                    <button onClick={() => removeTag(t)} className="ml-0.5" aria-label={`Remove tag ${t}`}>
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </Badge>
                ))}
                {tags.length === 0 && <span className="text-[10px] text-muted-foreground italic">none</span>}
              </div>
              <div className="flex gap-1.5">
                <Input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTag() } }}
                  className="h-7 text-xs flex-1"
                  placeholder="add tag"
                  disabled={submitting}
                />
                <Button variant="outline" size="sm" className="h-7" onClick={addTag} disabled={!tagInput.trim()}>
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Frontmatter</Label>
              <div className="flex gap-1.5">
                {(["none", "minimal", "full"] as FrontmatterMode[]).map((m) => (
                  <button
                    key={m}
                    type="button"
                    className={`text-xs px-2.5 py-1 rounded border ${fmMode === m ? "bg-primary/10 border-primary/40 text-primary" : "hover:bg-accent"}`}
                    onClick={() => setFmMode(m)}
                    disabled={submitting}
                  >
                    {m}
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground">
                {fmMode === "none" && "Saves just the content, no YAML header."}
                {fmMode === "minimal" && "Adds date + promoted_from + tags header."}
                {fmMode === "full" && "Adds full header with ISO timestamp and compiled-from source list."}
              </p>
            </div>

            {sources && sources.length > 0 && (
              <p className="text-[10px] text-muted-foreground italic">
                Saved document will include a <span className="font-mono">## Compiled from</span> footer listing the {sources.length} source{sources.length === 1 ? "" : "s"} this answer was derived from.
              </p>
            )}

            {error && <p className="text-xs text-destructive break-words">{error}</p>}
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel disabled={submitting}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleSubmit}
            disabled={submitting || loading || allTargets.length === 0 || !filename.trim()}
          >
            {submitting ? <><Loader2 className="h-3 w-3 animate-spin mr-1.5" />Filing…</> : "File"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function slugify(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
}
