import { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { CheckCircle2, Download, ExternalLink, Info, RefreshCw } from "lucide-react"

interface VersionResponse {
  current_version: string
  install_method: "docker" | "native" | "dev"
  update_check_enabled: boolean
}

interface UpdateCheckResponse {
  disabled?: boolean
  install_method: "docker" | "native" | "dev"
  current_version: string
  latest_version: string | null
  update_available: boolean
  release_url: string | null
  apply_command: string
  error: string | null
  dev_ahead: number | null
  dev_behind: number | null
}

const METHOD_LABEL: Record<string, string> = {
  docker: "Docker",
  native: "Native (pip)",
  dev: "Development (git)",
}

export function AboutPanel({ onEnableUpdateCheck }: { onEnableUpdateCheck: () => Promise<void> }) {
  const [version, setVersion] = useState<VersionResponse | null>(null)
  const [check, setCheck] = useState<UpdateCheckResponse | null>(null)
  const [checking, setChecking] = useState(false)

  const loadVersion = useCallback(async () => {
    try {
      const res = await api.get<VersionResponse>("/api/v1/version")
      setVersion(res)
    } catch (err) {
      void err
    }
  }, [])

  const runCheck = useCallback(async () => {
    setChecking(true)
    try {
      const res = await api.get<UpdateCheckResponse>("/api/v1/version/check")
      setCheck(res)
    } catch (err) {
      toast.error(`Update check failed: ${(err as Error).message}`)
    } finally {
      setChecking(false)
    }
  }, [])

  useEffect(() => {
    loadVersion()
  }, [loadVersion])

  // Auto-run a check when the panel opens, if the user has opted in.
  useEffect(() => {
    if (version?.update_check_enabled && !check) {
      runCheck()
    }
  }, [version, check, runCheck])

  if (!version) {
    return <div className="p-4 text-muted-foreground">Loading version info...</div>
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">About MarkdownKB</h2>
        <p className="text-sm text-muted-foreground">
          Version, install method, and update check.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Info className="h-4 w-4" />
            This Installation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <div className="text-muted-foreground">Version</div>
            <div className="font-mono">{version.current_version}</div>
            <div className="text-muted-foreground">Install method</div>
            <div>{METHOD_LABEL[version.install_method] ?? version.install_method}</div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <Download className="h-4 w-4" />
                Updates
              </CardTitle>
              <CardDescription className="mt-1">
                {version.update_check_enabled
                  ? "Checks PyPI or GitHub when you open this panel. No background polling."
                  : "Update checking is off. Enable it to see when a new version is available."}
              </CardDescription>
            </div>
            {version.update_check_enabled && (
              <Button variant="outline" size="sm" onClick={runCheck} disabled={checking}>
                <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${checking ? "animate-spin" : ""}`} />
                {checking ? "Checking…" : "Check now"}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {!version.update_check_enabled && (
            <Button
              onClick={async () => {
                await onEnableUpdateCheck()
                await loadVersion()
              }}
            >
              <Download className="h-3.5 w-3.5 mr-1.5" />
              Enable update checking
            </Button>
          )}

          {check?.disabled && (
            <p className="text-sm text-muted-foreground">Update checking is currently disabled.</p>
          )}

          {check && !check.disabled && check.error && (
            <p className="text-sm text-warning">
              Could not check for updates: {check.error}
            </p>
          )}

          {check && !check.disabled && !check.error && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <div className="text-muted-foreground">Latest version</div>
                <div className="font-mono">{check.latest_version ?? "—"}</div>
                {check.dev_behind !== null && (
                  <>
                    <div className="text-muted-foreground">Dev branch</div>
                    <div>
                      {check.dev_behind > 0 ? `${check.dev_behind} commits behind` : "up to date"}
                      {check.dev_ahead && check.dev_ahead > 0 ? `, ${check.dev_ahead} ahead` : ""}
                    </div>
                  </>
                )}
              </div>

              {check.update_available ? (
                <div className="rounded-md border border-warning/40 bg-warning/5 p-3 space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium text-warning">
                    <Badge variant="outline" className="border-warning text-warning">Update available</Badge>
                  </div>
                  <p className="text-sm">Run this command to update:</p>
                  <pre className="text-xs bg-muted rounded p-2 overflow-x-auto"><code>{check.apply_command}</code></pre>
                  <p className="text-xs text-muted-foreground">
                    Take a backup first via <strong>Settings → Backup &amp; Restore</strong>. After updating, restart the container.
                  </p>
                  {check.release_url && (
                    <Button asChild variant="outline" size="sm">
                      <a href={check.release_url} target="_blank" rel="noreferrer">
                        Release notes <ExternalLink className="h-3 w-3 ml-1.5" />
                      </a>
                    </Button>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-2 text-sm text-success">
                  <CheckCircle2 className="h-4 w-4" />
                  You&apos;re running the latest version.
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
