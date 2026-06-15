import { useCallback, useEffect, useMemo, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { EmptyHero } from "@/components/ui/empty-hero"
import { HelpTip } from "@/components/ui/help-tip"
import { AppSidebar } from "@/components/ui/app-sidebar"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { Sprout, Loader2, RefreshCw, GraduationCap, XCircle, Code2, Archive, AlertTriangle } from "lucide-react"
import { relativeTime, cn } from "@/lib/utils"

type DraftStatus = "draft" | "graduated" | "rejected"

interface Draft {
  id: string
  title: string
  body_md: string
  taxonomy_slot: string
  source_type: string
  source_ref: string
  run_id: string | null
  status: DraftStatus
  graduated_path: string | null
  reject_reason: string | null
  created_at: string
  updated_at: string
}

interface DraftsResponse {
  drafts: Draft[]
  total: number
  counts: Record<string, number>
}

const STATUS_FILTERS: { value: DraftStatus | "all"; label: string }[] = [
  { value: "draft", label: "Open" },
  { value: "graduated", label: "Graduated" },
  { value: "rejected", label: "Rejected" },
  { value: "all", label: "All" },
]

function SourceIcon({ type }: { type: string }) {
  if (type === "code") return <Code2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
  if (type === "bucket") return <Archive className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
  return <Sprout className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
}

export function CurateTab() {
  const [drafts, setDrafts] = useState<Draft[] | null>(null)
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<DraftStatus | "all">("draft")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Editable buffer for the selected draft (the per-candidate edit gate).
  const [editTitle, setEditTitle] = useState("")
  const [editBody, setEditBody] = useState("")
  const [editSlot, setEditSlot] = useState("")

  // Graduation target — the writable source the doc lands in.
  const [writableSources, setWritableSources] = useState<string[]>([])
  const [target, setTarget] = useState<string>("")
  const [busy, setBusy] = useState(false)
  const [pendingReject, setPendingReject] = useState<Draft | null>(null)

  const load = useCallback(() => {
    const q = filter === "all" ? "" : `?status=${filter}`
    api.get<DraftsResponse>(`/api/v1/curate/drafts${q}`)
      .then((r) => {
        setDrafts(r.drafts)
        setCounts(r.counts)
        setError(null)
        setSelectedId((prev) => prev ?? r.drafts[0]?.id ?? null)
      })
      .catch((err) => setError((err as Error).message))
  }, [filter])

  useEffect(() => { load() }, [load])

  // Writable sources for the graduation target dropdown.
  useEffect(() => {
    api.get<{ source_configs?: { path: string; writable: boolean }[] }>("/api/v1/settings")
      .then((r) => {
        const writable = (r.source_configs ?? []).filter((s) => s.writable).map((s) => s.path)
        setWritableSources(writable)
        setTarget((prev) => prev || writable[0] || "")
      })
      .catch(() => setWritableSources([]))
  }, [])

  const selected = useMemo(
    () => drafts?.find((d) => d.id === selectedId) ?? null,
    [drafts, selectedId],
  )

  // Sync the edit buffer when the selection changes.
  useEffect(() => {
    if (selected) {
      setEditTitle(selected.title)
      setEditBody(selected.body_md)
      setEditSlot(selected.taxonomy_slot)
    }
  }, [selected])

  const dirty = !!selected && (
    editTitle !== selected.title || editBody !== selected.body_md || editSlot !== selected.taxonomy_slot
  )

  async function saveEdits(): Promise<boolean> {
    if (!selected || !dirty) return true
    try {
      const res = await api.patch<{ shape_warnings: string[] }>(
        `/api/v1/curate/drafts/${selected.id}`,
        { title: editTitle, body_md: editBody, taxonomy_slot: editSlot },
      )
      res.shape_warnings?.forEach((w) => toast.warning(w))
      load()
      return true
    } catch (err) {
      toast.error((err as Error).message)
      return false
    }
  }

  async function handleSave() {
    setBusy(true)
    try {
      if (await saveEdits()) toast.success("Draft saved")
    } finally {
      setBusy(false)
    }
  }

  async function handleGraduate() {
    if (!selected) return
    if (!target) {
      toast.error("No writable source available — register the knowledge_docs tree first.")
      return
    }
    setBusy(true)
    try {
      // Persist any pending edits first so the graduated doc reflects them.
      if (dirty && !(await saveEdits())) return
      const res = await api.post<{ path: string }>(
        `/api/v1/curate/drafts/${selected.id}/graduate`,
        { target_source: target, overwrite: false },
      )
      toast.success(`Graduated to ${res.path}`)
      load()
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleReject(d: Draft, reason: string) {
    setBusy(true)
    try {
      await api.post(`/api/v1/curate/drafts/${d.id}/reject`, { reason })
      toast.success("Draft rejected")
      load()
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setBusy(false)
      setPendingReject(null)
    }
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center text-destructive p-8 text-center">
        Could not load curate drafts: {error}
      </div>
    )
  }

  if (drafts === null) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground gap-1.5">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading drafts...
      </div>
    )
  }

  const noWritable = writableSources.length === 0

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <AppSidebar
        header={
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-muted-foreground flex items-center gap-1.5">
              <Sprout className="h-4 w-4" />
              Curate
              <HelpTip>
                <p>
                  Review queue for the analyze–match–codify loop. Agents file
                  practiced-but-uncodified patterns here as <strong>drafts</strong>;
                  nothing enters the corpus until you graduate it. Two gates:
                  drafting is opt-in, and a human graduates each candidate by hand.
                </p>
              </HelpTip>
            </h3>
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={load} aria-label="Refresh drafts">
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
        }
      >
        <div className="p-2 space-y-2">
          <div className="flex flex-wrap gap-1">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                className={cn(
                  "text-[11px] rounded-md px-2 py-0.5 hover:bg-accent",
                  filter === f.value ? "bg-accent font-medium" : "text-muted-foreground",
                )}
                onClick={() => setFilter(f.value)}
              >
                {f.label}
                {f.value !== "all" && counts[f.value] ? ` (${counts[f.value]})` : ""}
              </button>
            ))}
          </div>

          <div className="space-y-0.5">
            {drafts.length === 0 && (
              <p className="text-[11px] text-muted-foreground px-3 py-2">No drafts in this view.</p>
            )}
            {drafts.map((d) => (
              <button
                key={d.id}
                type="button"
                className={cn(
                  "w-full text-left rounded-md px-3 py-2 text-sm hover:bg-accent",
                  selectedId === d.id && "bg-accent font-medium",
                )}
                onClick={() => setSelectedId(d.id)}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <SourceIcon type={d.source_type} />
                  <span className="truncate flex-1">{d.title}</span>
                  {d.status !== "draft" && (
                    <Badge variant="secondary" className="text-[10px] px-1 py-0">{d.status}</Badge>
                  )}
                </div>
                <div className="text-[11px] text-muted-foreground pl-5 truncate">
                  {d.taxonomy_slot} · {relativeTime(d.created_at)}
                </div>
              </button>
            ))}
          </div>
        </div>
      </AppSidebar>

      <div className="flex-1 min-w-0 min-h-0 flex flex-col">
        {selected ? (
          <ScrollArea className="flex-1">
            <div className="p-6 max-w-3xl space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Title</Label>
                <Input
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  disabled={selected.status !== "draft"}
                />
              </div>

              <div className="rounded-md border bg-muted/30 px-3 py-2 space-y-1 text-xs">
                <p className="text-[11px] font-medium text-muted-foreground">Provenance — where this draft came from</p>
                <div className="flex gap-x-5 gap-y-1 flex-wrap text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <SourceIcon type={selected.source_type} />
                    Source type: <span className="text-foreground">{selected.source_type || "—"}</span>
                  </span>
                  <span className="flex items-center gap-1 min-w-0">
                    Origin: <span className="text-foreground font-mono truncate max-w-md" title={selected.source_ref}>{selected.source_ref || "—"}</span>
                  </span>
                  <span>Run: <span className="text-foreground">{selected.run_id || "—"}</span></span>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
                  Taxonomy slot (graduation path)
                  <HelpTip>
                    <p>
                      Where this draft lands in the corpus when graduated, relative to
                      the chosen source — e.g. <span className="font-mono">patterns/error-handling</span>{" "}
                      writes <span className="font-mono">…/patterns/error-handling/&lt;slug&gt;.md</span>.
                      A slot ending in <span className="font-mono">.md</span> is used as the full file path.
                      Paths matching <span className="font-mono">global_ignore</span> are refused (they'd never be indexed).
                    </p>
                  </HelpTip>
                </Label>
                <Input
                  value={editSlot}
                  onChange={(e) => setEditSlot(e.target.value)}
                  placeholder="patterns/error-handling"
                  className="font-mono text-xs"
                  disabled={selected.status !== "draft"}
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Draft body</Label>
                <Textarea
                  value={editBody}
                  onChange={(e) => setEditBody(e.target.value)}
                  className="font-mono text-xs min-h-[320px]"
                  disabled={selected.status !== "draft"}
                />
              </div>

              {selected.status === "graduated" && (
                <p className="text-xs text-muted-foreground">
                  Graduated to <span className="font-mono">{selected.graduated_path}</span>
                </p>
              )}
              {selected.status === "rejected" && selected.reject_reason && (
                <p className="text-xs text-muted-foreground">Rejected: {selected.reject_reason}</p>
              )}

              {selected.status === "draft" && (
                <div className="border-t pt-4 space-y-3">
                  {dirty && (
                    <p className="text-[11px] text-amber-600 dark:text-amber-400 flex items-center gap-1">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      Unsaved edits — Save, or Graduate (which saves first).
                    </p>
                  )}
                  <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
                      Graduate into
                      <HelpTip>
                        <p>
                          The writable source this draft is written into. Graduating
                          composes the gated write: it saves the doc with provenance
                          frontmatter, appends to <span className="font-mono">log.md</span>, and makes a
                          version commit. Read-only sources can't be targets.
                        </p>
                      </HelpTip>
                    </Label>
                    <Select value={target} onValueChange={setTarget} disabled={noWritable}>
                      <SelectTrigger className="h-9 text-sm w-full">
                        <SelectValue placeholder={noWritable ? "No writable source" : "Choose target"} />
                      </SelectTrigger>
                      <SelectContent>
                        {writableSources.map((s) => (
                          <SelectItem key={s} value={s} className="text-sm font-mono">
                            <span title={s}>{s}</span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex gap-3 flex-wrap">
                    <Button variant="secondary" onClick={handleSave} disabled={busy || !dirty}>
                      Save
                    </Button>
                    <Button onClick={handleGraduate} disabled={busy || noWritable}>
                      <GraduationCap className="h-4 w-4 mr-1.5" />
                      Graduate
                    </Button>
                    <Button variant="outline" onClick={() => setPendingReject(selected)} disabled={busy}>
                      <XCircle className="h-4 w-4 mr-1.5" />
                      Reject
                    </Button>
                  </div>
                  {noWritable && (
                    <p className="text-[11px] text-muted-foreground flex items-center gap-1">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      Graduation unavailable — no writable source configured. Register the
                      canonical knowledge_docs tree as a writable source first.
                    </p>
                  )}
                </div>
              )}
            </div>
          </ScrollArea>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 gap-4 text-center">
            <EmptyHero icon={Sprout} label="No draft selected" />
            <p className="text-sm text-muted-foreground max-w-md">
              Curate holds bucket-C candidates — patterns an agent found practiced but
              uncodified — as drafts. Review each one and graduate it into the corpus, or
              reject it. Agents submit drafts via the <span className="font-mono">curate_submit_draft</span> tool.
            </p>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!pendingReject}
        onOpenChange={(o) => { if (!o) setPendingReject(null) }}
        title={pendingReject ? `Reject "${pendingReject.title}"?` : ""}
        description="The draft is kept (marked rejected) for provenance but never written to the corpus."
        confirmLabel="Reject"
        variant="destructive"
        onConfirm={() => { if (pendingReject) handleReject(pendingReject, "") }}
      />
    </div>
  )
}
