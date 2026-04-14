import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Loader2, Trash2, Download, GitBranch, Scissors, FileText, AlertCircle, Play } from "lucide-react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { usePathCheck } from "@/hooks/use-path-check"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import type { VersioningSourceStatus } from "@/lib/types"

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`
  return `${(n / 1024 ** 3).toFixed(2)} GB`
}

function formatRelative(iso: string | null): string {
  if (!iso) return "never"
  try {
    const delta = Date.now() - new Date(iso).getTime()
    const secs = Math.max(1, Math.floor(delta / 1000))
    if (secs < 60) return `${secs}s ago`
    if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
    if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
    return `${Math.floor(secs / 86400)}d ago`
  } catch {
    return iso
  }
}

/**
 * Row for a single source, showing its writable/versioned toggles plus
 * versioning stats and management actions. Used inside SourcesPanel.
 */
export function VersioningSourceRow({
  status,
  globalVersioningEnabled,
  onRemove,
  onUpdated,
}: {
  status: VersioningSourceStatus
  globalVersioningEnabled: boolean
  onRemove: () => void
  onUpdated: () => void
}) {
  const check = usePathCheck(status.path, 0)
  const [busy, setBusy] = useState(false)
  const [ignoreOpen, setIgnoreOpen] = useState(false)
  const [pruneOpen, setPruneOpen] = useState(false)

  const accessBadge = (() => {
    if (check.status === "ok") return null
    if (check.status === "needs_restart" || check.status === "bad_mount") {
      return <Badge variant="outline" className="text-yellow-600 dark:text-yellow-400 text-[10px] gap-1"><AlertCircle className="h-3 w-3" />Not mounted</Badge>
    }
    if (check.status === "not_found") {
      return <Badge variant="outline" className="text-destructive text-[10px] gap-1"><AlertCircle className="h-3 w-3" />Missing</Badge>
    }
    return null
  })()

  async function toggleWritable(v: boolean) {
    setBusy(true)
    try {
      await api.patch("/api/sources", { path: status.path, writable: v })
      toast.success(`${v ? "Enabled" : "Disabled"} writes for ${status.path}`)
      onUpdated()
    } catch (err) {
      toast.error(`Failed to update: ${(err as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  async function toggleVersioned(v: boolean) {
    setBusy(true)
    try {
      await api.patch("/api/sources", { path: status.path, versioned: v })
      toast.success(`${v ? "Enabled" : "Disabled"} versioning for ${status.path}`)
      onUpdated()
    } catch (err) {
      toast.error(`Failed to update: ${(err as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  async function handleInitRepo() {
    setBusy(true)
    try {
      await api.post("/api/versioning/init-repo", { path: status.path })
      toast.success("Managed repo initialised")
      onUpdated()
    } catch (err) {
      toast.error(`Init failed: ${(err as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  function handleExport() {
    const url = `/api/versioning/export?path=${encodeURIComponent(status.path)}`
    window.open(url, "_blank", "noopener")
  }

  const showInit = status.versioned && !status.initialised && check.status === "ok" && globalVersioningEnabled
  const showStats = status.versioned && status.initialised
  const canAct = status.versioned && status.initialised && globalVersioningEnabled

  return (
    <div className="rounded-md border p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className="font-mono text-sm flex-1 truncate">{status.path}</span>
        {accessBadge}
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onRemove}
          aria-label={`Remove ${status.path}`}
          disabled={busy}
        >
          <Trash2 className="h-3.5 w-3.5 text-destructive" />
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs">
        <label className="flex items-center gap-1.5 cursor-pointer">
          <Switch
            checked={status.writable}
            onCheckedChange={toggleWritable}
            disabled={busy}
          />
          <span>Writable</span>
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <Switch
            checked={status.versioned && globalVersioningEnabled}
            onCheckedChange={toggleVersioned}
            disabled={busy || !status.writable || !globalVersioningEnabled}
          />
          <span className={!globalVersioningEnabled ? "text-muted-foreground" : ""}>
            Versioned
            {!globalVersioningEnabled && (
              <span className="ml-1 text-[10px]">(globally off)</span>
            )}
          </span>
        </label>
        {showStats && (
          <span className="flex items-center gap-1 text-muted-foreground">
            <GitBranch className="h-3 w-3" />
            {status.commit_count} commits · {formatRelative(status.last_commit_date)} · {formatBytes(status.size_bytes)}
          </span>
        )}
        {showInit && (
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[11px] gap-1"
            onClick={handleInitRepo}
            disabled={busy}
          >
            {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
            Initialise repo
          </Button>
        )}
      </div>

      {canAct && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[11px] gap-1"
            onClick={() => setIgnoreOpen(true)}
            disabled={busy}
          >
            <FileText className="h-3 w-3" />
            Ignore rules
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[11px] gap-1"
            onClick={() => setPruneOpen(true)}
            disabled={busy || status.commit_count < 2}
          >
            <Scissors className="h-3 w-3" />
            Prune
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-6 text-[11px] gap-1"
            onClick={handleExport}
            disabled={busy}
          >
            <Download className="h-3 w-3" />
            Export
          </Button>
        </div>
      )}

      {ignoreOpen && (
        <IgnoreDialog
          path={status.path}
          open={ignoreOpen}
          onClose={() => setIgnoreOpen(false)}
        />
      )}
      {pruneOpen && (
        <PruneDialog
          path={status.path}
          commitCount={status.commit_count}
          open={pruneOpen}
          onClose={() => setPruneOpen(false)}
          onDone={() => { setPruneOpen(false); onUpdated() }}
        />
      )}
    </div>
  )
}

function IgnoreDialog({
  path, open, onClose,
}: {
  path: string
  open: boolean
  onClose: () => void
}) {
  const [contents, setContents] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    api.get<{ path: string; contents: string }>(
      `/api/versioning/ignore?path=${encodeURIComponent(path)}`,
    ).then((r) => setContents(r.contents))
      .catch((err) => toast.error(`Failed to load: ${(err as Error).message}`))
      .finally(() => setLoading(false))
  }, [open, path])

  async function handleSave() {
    setSaving(true)
    try {
      await api.put("/api/versioning/ignore", { path, contents })
      toast.success("Ignore rules saved")
      onClose()
    } catch (err) {
      toast.error(`Save failed: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <AlertDialogContent className="!max-w-2xl">
        <AlertDialogTitle className="text-sm">
          Ignore rules — <span className="font-mono text-xs">{path}</span>
        </AlertDialogTitle>
        <AlertDialogDescription className="text-xs">
          Gitignore-syntax patterns stored at <span className="font-mono">.git/info/exclude</span> inside the managed repo. One pattern per line. Matching files are skipped by auto-commit.
        </AlertDialogDescription>
        {loading ? (
          <div className="py-4 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            Loading...
          </div>
        ) : (
          <textarea
            className="w-full min-h-[220px] text-xs font-mono border rounded p-2 bg-background"
            value={contents}
            onChange={(e) => setContents(e.target.value)}
            spellCheck={false}
          />
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={saving}>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={handleSave} disabled={saving || loading}>
            {saving ? "Saving..." : "Save"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function PruneDialog({
  path, commitCount, open, onClose, onDone,
}: {
  path: string
  commitCount: number
  open: boolean
  onClose: () => void
  onDone: () => void
}) {
  const [mode, setMode] = useState<"keep" | "older">("keep")
  const [keepN, setKeepN] = useState(50)
  const [olderDays, setOlderDays] = useState(90)
  const [busy, setBusy] = useState(false)

  async function handleConfirm() {
    setBusy(true)
    try {
      const body: Record<string, unknown> = { path }
      if (mode === "keep") body.keep_last_n = keepN
      else body.older_than_days = olderDays
      const r = await api.post<{
        commits_before: number
        commits_after: number
      }>("/api/versioning/prune", body)
      toast.success(`Pruned ${r.commits_before - r.commits_after} commits`)
      onDone()
    } catch (err) {
      toast.error(`Prune failed: ${(err as Error).message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <AlertDialogContent>
        <AlertDialogTitle className="text-sm">Prune old commits</AlertDialogTitle>
        <AlertDialogDescription className="text-xs">
          Destructive — discards commits and runs garbage collection. Current repo has {commitCount} commits. Cannot be undone.
        </AlertDialogDescription>
        <div className="space-y-3 py-2">
          <label className="flex items-center gap-2 text-xs cursor-pointer">
            <input
              type="radio"
              checked={mode === "keep"}
              onChange={() => setMode("keep")}
              disabled={busy}
            />
            Keep the most recent
            <Input
              type="number"
              value={keepN}
              onChange={(e) => setKeepN(Number(e.target.value))}
              disabled={busy || mode !== "keep"}
              className="h-7 w-20 text-xs"
              min={1}
            />
            commits
          </label>
          <label className="flex items-center gap-2 text-xs cursor-pointer">
            <input
              type="radio"
              checked={mode === "older"}
              onChange={() => setMode("older")}
              disabled={busy}
            />
            Discard commits older than
            <Input
              type="number"
              value={olderDays}
              onChange={(e) => setOlderDays(Number(e.target.value))}
              disabled={busy || mode !== "older"}
              className="h-7 w-20 text-xs"
              min={1}
            />
            days
          </label>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={handleConfirm} disabled={busy}>
            {busy ? "Pruning..." : "Prune"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
