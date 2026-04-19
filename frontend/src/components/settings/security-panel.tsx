import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ShieldCheck, ShieldAlert, KeyRound, CheckCircle2, AlertTriangle, XCircle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface SecurityCheck {
  auth_enabled: boolean
  network_exposed: boolean
  api_key_strength: "none" | "weak" | "ok"
  data_dir_world_readable: boolean
  data_dir: string
  mcp_enabled: boolean
}

type CheckStatus = "pass" | "warn" | "fail"

interface CheckItem {
  label: string
  status: CheckStatus
  detail: string
}

function buildChecklist(s: SecurityCheck): CheckItem[] {
  const items: CheckItem[] = []

  // Auth
  if (s.auth_enabled) {
    items.push({ label: "Authentication", status: "pass", detail: "API key is configured." })
  } else if (s.network_exposed) {
    items.push({ label: "Authentication", status: "fail", detail: "No API key set and the server is network-accessible. Anyone on your network can access this instance." })
  } else {
    items.push({ label: "Authentication", status: "warn", detail: "No API key set, but the server is only accessible from localhost." })
  }

  // Network exposure
  if (!s.network_exposed) {
    items.push({ label: "Network exposure", status: "pass", detail: "Server is bound to localhost only." })
  } else if (s.auth_enabled) {
    items.push({ label: "Network exposure", status: "warn", detail: "Server is accessible on the network. Authentication is enabled, so access is restricted." })
  } else {
    items.push({ label: "Network exposure", status: "fail", detail: "Server is accessible on the network without authentication." })
  }

  // API key strength
  if (s.api_key_strength === "ok") {
    items.push({ label: "API key strength", status: "pass", detail: "Key length is sufficient." })
  } else if (s.api_key_strength === "weak") {
    items.push({ label: "API key strength", status: "warn", detail: "API key is shorter than 16 characters. Consider using a longer, randomly generated key." })
  } else {
    items.push({ label: "API key strength", status: "warn", detail: "No API key configured. See instructions below to set one." })
  }

  // Data directory permissions
  if (s.data_dir_world_readable) {
    items.push({ label: "Data directory permissions", status: "warn", detail: `${s.data_dir} is world-readable. Consider restricting to the owning user only (chmod 700).` })
  } else {
    items.push({ label: "Data directory permissions", status: "pass", detail: "Data directory is not world-readable." })
  }

  // MCP
  if (s.mcp_enabled) {
    items.push({ label: "MCP server", status: "warn", detail: "MCP features are enabled. Verify the MCP server is not publicly exposed if running on a shared network." })
  } else {
    items.push({ label: "MCP server", status: "pass", detail: "No MCP features enabled." })
  }

  return items
}

function StatusIcon({ status }: { status: CheckStatus }) {
  if (status === "pass") return <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
  if (status === "warn") return <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
  return <XCircle className="h-4 w-4 text-destructive shrink-0" />
}

export function SecurityPanel() {
  const [check, setCheck] = useState<SecurityCheck | null>(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    api.get<SecurityCheck>("/api/v1/settings/security-check")
      .then(setCheck)
      .catch(() => { /* best-effort */ })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const overallOk = check && buildChecklist(check).every(i => i.status === "pass")

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold mb-1">Security</h2>
          <p className="text-sm text-muted-foreground">
            Security checks for this MarkdownKB instance
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={cn("h-3.5 w-3.5 mr-1.5", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {check && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              {overallOk
                ? <ShieldCheck className="h-4 w-4 text-green-500" />
                : <ShieldAlert className="h-4 w-4 text-amber-500" />}
              Security Checklist
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {buildChecklist(check).map((item) => (
              <div key={item.label} className="flex items-start gap-2.5">
                <StatusIcon status={item.status} />
                <div className="min-w-0">
                  <p className="text-sm font-medium leading-none mb-0.5">{item.label}</p>
                  <p className="text-xs text-muted-foreground">{item.detail}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <KeyRound className="h-4 w-4" />
            Setting an API Key
          </CardTitle>
          <CardDescription>
            Restrict access by requiring a key on every request
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <p className="text-muted-foreground">
            Choose one of the two methods below, then restart the container or process.
          </p>

          <div className="space-y-1.5">
            <p className="font-medium">Option 1 — Secret file</p>
            <p className="text-muted-foreground">
              Create a file named <code className="bg-muted px-1 rounded font-mono">markdownkb_api_key</code> inside
              the <code className="bg-muted px-1 rounded font-mono">secrets/</code> subdirectory of your data volume and write
              your chosen key as its only content (no newline needed).
            </p>
            <div className="bg-muted rounded-md px-3 py-2 font-mono text-xs leading-relaxed">
              <span className="text-muted-foreground"># Docker example (data volume mounted at /data)</span>
              {"\n"}echo -n "your-secret-key" &gt; /data/secrets/markdownkb_api_key
            </div>
          </div>

          <div className="space-y-1.5">
            <p className="font-medium">Option 2 — Environment variable</p>
            <p className="text-muted-foreground">
              Set the <code className="bg-muted px-1 rounded font-mono">MARKDOWNKB_API_KEY</code> environment variable
              before starting the process. In Docker Compose, add it to your <code className="bg-muted px-1 rounded font-mono">environment:</code> block.
            </p>
            <div className="bg-muted rounded-md px-3 py-2 font-mono text-xs">
              MARKDOWNKB_API_KEY=your-secret-key
            </div>
          </div>

          <div className="space-y-1.5 pt-1 border-t">
            <p className="font-medium">Using the key</p>
            <p className="text-muted-foreground">
              Pass the key in the <code className="bg-muted px-1 rounded font-mono">X-MarkdownKB-Key</code> header on every API request.
              The browser session is configured automatically when you open the app — direct API callers (scripts, MCP, CLI) must include the header explicitly.
            </p>
            <div className="bg-muted rounded-md px-3 py-2 font-mono text-xs">
              curl -H "X-MarkdownKB-Key: your-secret-key" http://localhost:3000/api/v1/health
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
