import { useEffect, useState } from "react"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { History, Loader2, RotateCcw } from "lucide-react"
import { api } from "@/lib/api"
import { toast } from "sonner"

interface Commit {
  sha: string
  date: string
  subject: string
}

interface HistoryResponse {
  path: string
  source: string
  commits: Commit[]
}

interface DiffResponse {
  sha: string
  path: string
  diff: string
}

interface RestoreResponse {
  status: string
  restored_from: string
  new_commit: string | null
}

/**
 * Revision-history viewer for a single file. Lists commits, shows the
 * unified diff for the selected commit, and lets the user restore an
 * older revision (which writes back as a new commit — no history
 * rewrite).
 */
export function HistoryDialog({
  open,
  path,
  onClose,
  onRestored,
}: {
  open: boolean
  path: string | null
  onClose: () => void
  onRestored?: () => void
}) {
  const [commits, setCommits] = useState<Commit[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [diff, setDiff] = useState<string>("")
  const [diffLoading, setDiffLoading] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [pendingRestore, setPendingRestore] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !path) return
    setCommits(null)
    setLoadError(null)
    setSelected(null)
    setDiff("")
    api.get<HistoryResponse>(
      `/api/v1/versioning/history?path=${encodeURIComponent(path)}`,
    ).then((r) => {
      setCommits(r.commits)
      if (r.commits.length > 0) setSelected(r.commits[0].sha)
    }).catch((err) => {
      const msg = (err as Error).message || "Unknown error"
      setLoadError(msg)
    })
  }, [open, path])

  useEffect(() => {
    if (!open || !path || !selected) {
      setDiff("")
      return
    }
    setDiffLoading(true)
    api.get<DiffResponse>(
      `/api/v1/versioning/diff?path=${encodeURIComponent(path)}&commit=${encodeURIComponent(selected)}`,
    ).then((r) => setDiff(r.diff || "(no diff)"))
      .catch((err) => setDiff(`Error loading diff: ${(err as Error).message}`))
      .finally(() => setDiffLoading(false))
  }, [open, path, selected])

  const handleRestore = async (sha: string) => {
    if (!path) return
    setRestoring(true)
    try {
      const r = await api.post<RestoreResponse>("/api/v1/versioning/restore", {
        path,
        commit: sha,
      })
      toast.success(`Restored from ${sha.slice(0, 8)} (new commit ${r.new_commit?.slice(0, 8) ?? "none"})`)
      setPendingRestore(null)
      onRestored?.()
      // Refresh history to include the new commit.
      const refreshed = await api.get<HistoryResponse>(
        `/api/v1/versioning/history?path=${encodeURIComponent(path)}`,
      )
      setCommits(refreshed.commits)
      if (refreshed.commits.length > 0) setSelected(refreshed.commits[0].sha)
    } catch (err) {
      toast.error(`Restore failed: ${(err as Error).message}`)
    } finally {
      setRestoring(false)
    }
  }

  const filename = path?.split("/").pop() ?? ""
  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString()
    } catch {
      return iso
    }
  }

  const renderDiff = (text: string) => {
    const lines = text.split("\n")
    return lines.map((line, i) => {
      let cls = ""
      if (line.startsWith("+") && !line.startsWith("+++")) cls = "text-green-600 dark:text-green-400"
      else if (line.startsWith("-") && !line.startsWith("---")) cls = "text-red-600 dark:text-red-400"
      else if (line.startsWith("@@")) cls = "text-blue-600 dark:text-blue-400"
      else if (line.startsWith("diff ") || line.startsWith("index ") || line.startsWith("+++") || line.startsWith("---"))
        cls = "text-muted-foreground"
      return (
        <div key={i} className={cls}>
          {line || "\u00A0"}
        </div>
      )
    })
  }

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <AlertDialogContent className="!max-w-5xl !h-[80vh] flex flex-col">
        <AlertDialogTitle className="flex items-center gap-2">
          <History className="h-4 w-4" />
          History — <span className="font-mono text-xs">{filename}</span>
        </AlertDialogTitle>
        <AlertDialogDescription className="text-xs">
          Each mdkb write creates a commit. Select a commit to see the diff or restore it.
        </AlertDialogDescription>

        <div className="flex-1 min-h-0 grid grid-cols-[280px_1fr] gap-3 overflow-hidden">
          {/* Commit list */}
          <div className="border rounded-md overflow-hidden flex flex-col">
            <div className="px-3 py-2 border-b text-xs font-medium text-muted-foreground">
              Commits {commits ? `(${commits.length})` : ""}
            </div>
            <ScrollArea className="flex-1 min-h-0">
              {loadError ? (
                <p className="text-xs text-destructive p-3">{loadError}</p>
              ) : commits === null ? (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground p-3">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Loading...
                </div>
              ) : commits.length === 0 ? (
                <p className="text-xs text-muted-foreground p-3 italic">
                  No commits yet — this file hasn't been written by mdkb.
                </p>
              ) : (
                <ul className="text-xs">
                  {commits.map((c, i) => {
                    const isCurrent = i === 0
                    const isSelected = selected === c.sha
                    return (
                      <li
                        key={c.sha}
                        onClick={() => setSelected(c.sha)}
                        className={`px-3 py-2 border-b cursor-pointer hover:bg-muted/50 ${isSelected ? "bg-primary/10" : ""}`}
                      >
                        <div className="flex items-center justify-between gap-1 mb-0.5">
                          <span className="font-mono text-[10px] text-muted-foreground">
                            {c.sha.slice(0, 8)}
                          </span>
                          {isCurrent && (
                            <span className="text-[10px] px-1 rounded bg-primary/20 text-primary">current</span>
                          )}
                        </div>
                        <div className="font-medium truncate" title={c.subject}>
                          {c.subject}
                        </div>
                        <div className="text-[10px] text-muted-foreground">
                          {formatDate(c.date)}
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </ScrollArea>
          </div>

          {/* Diff viewer */}
          <div className="border rounded-md overflow-hidden flex flex-col">
            <div className="px-3 py-2 border-b flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {selected ? `Diff @ ${selected.slice(0, 8)}` : "Select a commit"}
              </span>
              {selected && commits && commits.length > 0 && selected !== commits[0].sha && (
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 text-xs gap-1"
                  onClick={() => setPendingRestore(selected)}
                  disabled={restoring}
                >
                  <RotateCcw className="h-3 w-3" />
                  Restore this version
                </Button>
              )}
            </div>
            <ScrollArea className="flex-1 min-h-0 p-3">
              {diffLoading ? (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Loading diff...
                </div>
              ) : diff ? (
                <pre className="font-mono text-[11px] leading-snug whitespace-pre-wrap break-all">
                  {renderDiff(diff)}
                </pre>
              ) : (
                <p className="text-xs text-muted-foreground italic">No diff to show.</p>
              )}
            </ScrollArea>
          </div>
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel onClick={onClose} disabled={restoring}>Close</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>

      {/* Restore confirmation */}
      {pendingRestore && (
        <AlertDialog open onOpenChange={(o) => { if (!o) setPendingRestore(null) }}>
          <AlertDialogContent>
            <AlertDialogTitle>Restore this version?</AlertDialogTitle>
            <AlertDialogDescription className="text-xs">
              The contents of <span className="font-mono">{filename}</span> at <span className="font-mono">{pendingRestore.slice(0, 8)}</span> will be written back to disk as a new commit. Nothing is lost — the current version stays in history.
            </AlertDialogDescription>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={restoring} onClick={() => setPendingRestore(null)}>Cancel</AlertDialogCancel>
              <Button
                onClick={() => pendingRestore && handleRestore(pendingRestore)}
                disabled={restoring}
              >
                {restoring ? <><Loader2 className="h-3 w-3 animate-spin mr-1.5" /> Restoring…</> : "Restore"}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </AlertDialog>
  )
}
