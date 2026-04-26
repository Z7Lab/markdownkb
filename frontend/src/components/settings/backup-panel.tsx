import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { api } from "@/lib/api"
import { formatBytes } from "@/lib/utils"
import { toast } from "sonner"
import { Archive, Download, Upload, RefreshCw, AlertTriangle, CheckCircle2 } from "lucide-react"

interface BackupStatus {
  data_dir: string
  data_size_bytes: number
  mdkb_version: string
  restart_pending: {
    restored_at?: string
    from_backup_id?: string
    from_backup_created_at?: string
    from_mdkb_version?: string
    backup_embedding_model?: string
    current_embedding_model?: string
    model_mismatch?: boolean
  } | null
}

interface DatabaseStats {
  chat_history: { path: string; size_bytes: number }
  search_history: { path: string; size_bytes: number }
  vector_database: { size_bytes: number; data_directory: string }
  plugin_databases?: Array<{ name: string; path: string; size_bytes: number }>
}

interface BackupManifest {
  format_version: number
  mdkb_version: string
  created_at: string
  id: string
  contents: string[]
  options: { include_config: boolean; include_sources: boolean }
  sources: string[]
  data_dir: string
}

function SectionHeading({ title, description }: { title: string; description: string }) {
  return (
    <div className="space-y-1 pb-2">
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  )
}

async function triggerDownload(res: Response, fallbackName: string) {
  const blob = await res.blob()
  const cd = res.headers.get("content-disposition") ?? ""
  const match = /filename=([^;]+)/.exec(cd)
  const filename = match ? match[1]!.replace(/"/g, "") : fallbackName
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}


export function BackupPanel() {
  const [status, setStatus] = useState<BackupStatus | null>(null)
  const [dbStats, setDbStats] = useState<DatabaseStats | null>(null)
  const [includeConfig, setIncludeConfig] = useState(true)
  const [includeSources, setIncludeSources] = useState(false)
  const [includeChromadb, setIncludeChromadb] = useState(true)
  const [includeMarkdown, setIncludeMarkdown] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [downloadingMarkdown, setDownloadingMarkdown] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [pendingRestore, setPendingRestore] = useState<{ file: File; manifest: BackupManifest } | null>(null)
  const [applyConfig, setApplyConfig] = useState(true)
  const [applySources, setApplySources] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const loadStatus = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([
        api.get<BackupStatus>("/api/v1/backups/status"),
        api.get<DatabaseStats>("/api/v1/settings/database-stats").catch(() => null),
      ])
      setStatus(s)
      setDbStats(d)
    } catch (err) {
      void err
    }
  }, [])

  useEffect(() => {
    loadStatus()
  }, [loadStatus])

  // ── Downloads ──────────────────────────────────────────────────────────

  const handleDownloadMarkdown = async () => {
    setDownloadingMarkdown(true)
    try {
      const res = await api.fetchRaw("GET", "/api/v1/export/markdown")
      await triggerDownload(res, "mdkb-markdown.zip")
      toast.success("Markdown archive downloaded")
    } catch (err) {
      toast.error(`Export failed: ${(err as Error).message}`)
    } finally {
      setDownloadingMarkdown(false)
    }
  }

  const handleDownloadBackup = async () => {
    setDownloading(true)
    try {
      const res = await api.fetchRaw(
        "POST",
        "/api/v1/backups/create",
        JSON.stringify({
          include_config: includeConfig,
          include_sources: includeSources,
          include_chromadb: includeChromadb,
          include_markdown: includeMarkdown,
        }),
        { "Content-Type": "application/json" },
      )
      await triggerDownload(res, "mdkb-backup.tar.gz")
      toast.success("System backup downloaded")
    } catch (err) {
      toast.error(`Backup failed: ${(err as Error).message}`)
    } finally {
      setDownloading(false)
    }
  }

  // ── Restore ────────────────────────────────────────────────────────────

  const handleFilePick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setPreviewing(true)
    try {
      const fd = new FormData()
      fd.append("file", file)
      const data = await api.upload<{ manifest: BackupManifest }>("/api/v1/backups/preview", fd)
      setPendingRestore({ file, manifest: data.manifest })
    } catch (err) {
      toast.error(`Preview failed: ${(err as Error).message}`)
    } finally {
      setPreviewing(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  const handleConfirmRestore = async () => {
    if (!pendingRestore) return
    setRestoring(true)
    try {
      const fd = new FormData()
      fd.append("file", pendingRestore.file)
      fd.append("apply_config", String(applyConfig))
      fd.append("apply_sources", String(applySources))
      await api.upload("/api/v1/backups/restore", fd)
      toast.success("Restore complete — restart the container to use the new data")
      setPendingRestore(null)
      await loadStatus()
    } catch (err) {
      toast.error(`Restore failed: ${(err as Error).message}`)
    } finally {
      setRestoring(false)
    }
  }

  const handleClearMarker = async () => {
    try {
      await api.del("/api/v1/backups/restart-marker")
      await loadStatus()
    } catch (err) {
      toast.error(`Failed: ${(err as Error).message}`)
    }
  }

  // ── Size summary ────────────────────────────────────────────────────────

  const sizeRows: { label: string; bytes: number }[] = dbStats ? [
    { label: "Chat history", bytes: dbStats.chat_history.size_bytes },
    { label: "Search history", bytes: dbStats.search_history.size_bytes },
    { label: "Vector store", bytes: dbStats.vector_database.size_bytes },
    ...( dbStats.plugin_databases?.map(d => ({ label: d.name, bytes: d.size_bytes })) ?? []),
  ] : []
  const totalBytes = sizeRows.reduce((s, r) => s + r.bytes, 0)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Backup &amp; Restore</h2>
        <p className="text-sm text-muted-foreground">
          Export your knowledge as plain files or a full system backup. Restore a previous state after upgrades or data loss.
        </p>
      </div>

      {status?.restart_pending && (
        <Card className="border-warning">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-warning">
              <AlertTriangle className="h-4 w-4" />
              Restart required
            </CardTitle>
            <CardDescription className="space-y-2">
              <span className="block">
                A restore was applied at {status.restart_pending.restored_at}.
                Run <code className="bg-muted px-1 rounded">make docker-restart</code> for the new data to take effect.
              </span>
              {status.restart_pending.model_mismatch && (
                <span className="block text-destructive font-medium">
                  Embedding model mismatch: the backup was built with{" "}
                  <code className="bg-muted px-1 rounded">{status.restart_pending.backup_embedding_model}</code>{" "}
                  but you are currently using{" "}
                  <code className="bg-muted px-1 rounded">{status.restart_pending.current_embedding_model}</code>.
                  After restarting, go to Settings → Database and clear the vector store, then re-index — or switch back to the backup&apos;s model before indexing.
                </span>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" size="sm" onClick={handleClearMarker}>
              <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
              I&apos;ve restarted — clear this notice
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ── Quick Export ─────────────────────────────────────────────── */}

      <SectionHeading
        title="Quick Export"
        description="Download every indexed markdown file as a portable zip — source files, bucket documents, and wiki output. No databases or vector embeddings. Use this to pull your content without taking a full system backup."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Archive className="h-4 w-4" />
            Markdown Archive
          </CardTitle>
          <CardDescription className="mt-1">
            A <code>.zip</code> organised into three folders: <code>sources/</code> (files from your watched directories),{" "}
            <code>buckets/</code> (bucket documents, including those uploaded directly — read from the database),{" "}
            and <code>wikis/</code> (wiki_compile output, if enabled).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={handleDownloadMarkdown} disabled={downloadingMarkdown}>
            <Archive className="h-3.5 w-3.5 mr-1.5" />
            {downloadingMarkdown ? "Building archive…" : "Download Markdown Archive"}
          </Button>
        </CardContent>
      </Card>

      <Separator />

      {/* ── System Backups ────────────────────────────────────────────── */}

      <SectionHeading
        title="System Backups"
        description="Portable archives that capture the full application state — databases, vector embeddings, and configuration. Both formats below are restorable via the Restore section."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Download className="h-4 w-4" />
            Create System Backup
          </CardTitle>
          <CardDescription className="mt-1">
            A <code>.tar.gz</code> containing all SQLite databases (chats, searches, plans, tags, scopes),
            the ChromaDB vector store, and optionally your configuration.
            Restoring this archive recovers your full conversation history, search history,
            plans, scopes, buckets, tags, and all indexed vectors.
            Secrets and embedding model weights are never included.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {sizeRows.length > 0 && (
            <div className="rounded-md border text-sm">
              <table className="w-full">
                <tbody>
                  {sizeRows.map((row) => (
                    <tr key={row.label} className="border-b last:border-0">
                      <td className="px-3 py-1.5 text-muted-foreground">{row.label}</td>
                      <td className="px-3 py-1.5 text-right font-mono">{formatBytes(row.bytes)}</td>
                    </tr>
                  ))}
                  <tr className="bg-muted/40 font-medium">
                    <td className="px-3 py-1.5">Estimated backup size</td>
                    <td className="px-3 py-1.5 text-right font-mono">{formatBytes(totalBytes)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}

          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <Checkbox
                id="include-config"
                checked={includeConfig}
                onCheckedChange={(v) => setIncludeConfig(v === true)}
              />
              <div className="grid gap-0.5 leading-none">
                <Label htmlFor="include-config" className="text-sm font-normal">
                  Include configuration
                </Label>
                <p className="text-xs text-muted-foreground">
                  settings.yaml and Docker mount overrides — skip if restoring on a machine with different paths
                </p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Checkbox
                id="include-chromadb"
                checked={includeChromadb}
                onCheckedChange={(v) => setIncludeChromadb(v === true)}
              />
              <div className="grid gap-0.5 leading-none">
                <Label htmlFor="include-chromadb" className="text-sm font-normal">
                  Include vector embeddings
                </Label>
                <p className="text-xs text-muted-foreground">
                  the ChromaDB vector store — usually the largest part; skip if you plan to re-index after restoring
                </p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Checkbox
                id="include-sources"
                checked={includeSources}
                onCheckedChange={(v) => setIncludeSources(v === true)}
              />
              <div className="grid gap-0.5 leading-none">
                <Label htmlFor="include-sources" className="text-sm font-normal">
                  Include source files
                </Label>
                <p className="text-xs text-muted-foreground">
                  copies all watched directories — usually large; only enable when moving machines or sharing a complete KB
                </p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Checkbox
                id="include-markdown"
                checked={includeMarkdown}
                onCheckedChange={(v) => setIncludeMarkdown(v === true)}
              />
              <div className="grid gap-0.5 leading-none">
                <Label htmlFor="include-markdown" className="text-sm font-normal">
                  Include markdown content
                </Label>
                <p className="text-xs text-muted-foreground">
                  adds a <code>markdown/</code> subtree of every indexed file (sources, bucket documents, wiki output) —
                  useful for archival or migration; not applied during restore
                </p>
              </div>
            </div>
          </div>

          <Button onClick={handleDownloadBackup} disabled={downloading}>
            <Download className="h-3.5 w-3.5 mr-1.5" />
            {downloading ? "Building backup…" : "Download System Backup"}
          </Button>
        </CardContent>
      </Card>

      <Separator />

      {/* ── Restore ───────────────────────────────────────────────────── */}

      <SectionHeading
        title="Restore"
        description="Apply a system backup or full snapshot. All current databases and vector data will be replaced. You'll need to restart the container after restoring."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Upload className="h-4 w-4" />
            Restore from Backup
          </CardTitle>
          <CardDescription className="mt-1">
            Upload a <code>.tar.gz</code> produced by &quot;Create System Backup&quot; or &quot;Download Full Snapshot&quot;.
            The manifest is shown for confirmation before any data is changed.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <input
            ref={fileInputRef}
            type="file"
            accept=".tar.gz,application/gzip"
            className="hidden"
            onChange={handleFilePick}
          />
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={previewing || restoring}
          >
            <Upload className="h-3.5 w-3.5 mr-1.5" />
            {previewing ? "Reading manifest…" : "Choose Backup File…"}
          </Button>
        </CardContent>
      </Card>

      <div className="flex items-center gap-2 pt-2">
        <Button variant="outline" size="sm" onClick={loadStatus}>
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
          Refresh
        </Button>
      </div>

      <ConfirmDialog
        open={!!pendingRestore}
        onOpenChange={(open) => {
          if (!open) setPendingRestore(null)
        }}
        title="Restore this backup?"
        description={
          pendingRestore ? (
            <div className="space-y-3">
              <div className="text-sm space-y-1">
                <div><span className="text-muted-foreground">Created:</span> {pendingRestore.manifest.created_at}</div>
                <div><span className="text-muted-foreground">From mdkb:</span> {pendingRestore.manifest.mdkb_version}</div>
                <div><span className="text-muted-foreground">Contents:</span> {pendingRestore.manifest.contents.join(", ")}</div>
              </div>
              <div className="rounded-md bg-warning/10 text-warning p-3 text-sm">
                <strong>Warning:</strong> all current databases, vector embeddings, and plugin data will be replaced.
                Secrets and embedding model weights will be preserved.
              </div>
              <div className="space-y-2">
                {pendingRestore.manifest.options.include_config && (
                  <div className="flex items-start gap-2">
                    <Checkbox
                      id="apply-config"
                      checked={applyConfig}
                      onCheckedChange={(v) => setApplyConfig(v === true)}
                    />
                    <Label htmlFor="apply-config" className="text-sm font-normal">
                      Apply configuration from backup (settings.yaml)
                    </Label>
                  </div>
                )}
                {pendingRestore.manifest.options.include_sources && (
                  <div className="flex items-start gap-2">
                    <Checkbox
                      id="apply-sources"
                      checked={applySources}
                      onCheckedChange={(v) => setApplySources(v === true)}
                    />
                    <Label htmlFor="apply-sources" className="text-sm font-normal">
                      Unpack source files into <code>restored-sources/</code> (manual copy required)
                    </Label>
                  </div>
                )}
              </div>
            </div>
          ) : ""
        }
        confirmLabel={restoring ? "Restoring…" : "Restore"}
        variant="destructive"
        onConfirm={handleConfirmRestore}
      />
    </div>
  )
}
