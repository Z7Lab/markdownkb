import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { api, getApiKey } from "@/lib/api"
import { toast } from "sonner"
import { Download, Upload, RefreshCw, AlertTriangle, CheckCircle2 } from "lucide-react"

interface BackupStatus {
  data_dir: string
  data_size_bytes: number
  mdkb_version: string
  restart_pending: {
    restored_at?: string
    from_backup_id?: string
    from_backup_created_at?: string
    from_mdkb_version?: string
  } | null
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

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB", "TB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

function authHeaders(): Record<string, string> {
  const key = getApiKey()
  return key ? { "X-MarkdownKB-Key": key } : {}
}

export function BackupPanel() {
  const [status, setStatus] = useState<BackupStatus | null>(null)
  const [includeConfig, setIncludeConfig] = useState(true)
  const [includeSources, setIncludeSources] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [pendingRestore, setPendingRestore] = useState<{ file: File; manifest: BackupManifest } | null>(null)
  const [applyConfig, setApplyConfig] = useState(true)
  const [applySources, setApplySources] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const loadStatus = useCallback(async () => {
    try {
      const res = await api.get<BackupStatus>("/api/v1/backups/status")
      setStatus(res)
    } catch (err) {
      void err
    }
  }, [])

  useEffect(() => {
    loadStatus()
  }, [loadStatus])

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const res = await fetch("/api/v1/backups/create", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          include_config: includeConfig,
          include_sources: includeSources,
        }),
      })
      if (!res.ok) {
        throw new Error(`${res.status}: ${await res.text()}`)
      }
      const blob = await res.blob()
      const cd = res.headers.get("content-disposition") ?? ""
      const match = /filename=([^;]+)/.exec(cd)
      const filename = match ? match[1].replace(/"/g, "") : "mdkb-backup.tar.gz"
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success("Backup downloaded")
    } catch (err) {
      toast.error(`Backup failed: ${(err as Error).message}`)
    } finally {
      setDownloading(false)
    }
  }

  const handleFilePick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setPreviewing(true)
    try {
      const fd = new FormData()
      fd.append("file", file)
      const res = await fetch("/api/v1/backups/preview", {
        method: "POST",
        body: fd,
        headers: authHeaders(),
      })
      if (!res.ok) {
        throw new Error(`${res.status}: ${await res.text()}`)
      }
      const data = (await res.json()) as { manifest: BackupManifest }
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
      const res = await fetch("/api/v1/backups/restore", {
        method: "POST",
        body: fd,
        headers: authHeaders(),
      })
      if (!res.ok) {
        throw new Error(`${res.status}: ${await res.text()}`)
      }
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

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Backup &amp; Restore</h2>
        <p className="text-sm text-muted-foreground">
          Export your full MarkdownKB state — databases, vector store, plugin data — as a portable archive.
          Restore on another machine or after a disaster.
        </p>
      </div>

      {status?.restart_pending && (
        <Card className="border-warning">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-warning">
              <AlertTriangle className="h-4 w-4" />
              Restart required
            </CardTitle>
            <CardDescription>
              A restore was applied at {status.restart_pending.restored_at}.
              Run <code className="bg-muted px-1 rounded">make docker-restart</code> for the new data to take effect.
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

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <Download className="h-4 w-4" />
                Create Backup
              </CardTitle>
              <CardDescription className="mt-1">
                Downloads a single .tar.gz with all databases, vector embeddings, and plugin data.
                Secrets and embedding model weights are never included.
              </CardDescription>
            </div>
            <div className="text-right">
              <p className="text-sm font-medium">{status ? formatBytes(status.data_size_bytes) : "—"}</p>
              <p className="text-xs text-muted-foreground">data dir size</p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
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
                  settings.yaml and Docker mount overrides — recommended unless restoring on a machine with different paths
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
                  copies all watched directories into the archive — usually large; only enable for &quot;moving machines&quot; or sharing a complete KB
                </p>
              </div>
            </div>
          </div>
          <Button onClick={handleDownload} disabled={downloading}>
            <Download className="h-3.5 w-3.5 mr-1.5" />
            {downloading ? "Building backup…" : "Download Backup"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Upload className="h-4 w-4" />
            Restore from Backup
          </CardTitle>
          <CardDescription className="mt-1">
            Upload a .tar.gz produced by &quot;Create Backup&quot;. Existing data will be replaced.
            You&apos;ll need to restart the container after restoring.
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
