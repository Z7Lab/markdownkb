import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ShieldAlert, ShieldCheck, KeyRound } from "lucide-react"

interface HealthStatus {
  auth_enabled: boolean
  network_exposed: boolean
}

export function SecurityPanel() {
  const [status, setStatus] = useState<HealthStatus | null>(null)

  useEffect(() => {
    api.get<HealthStatus>("/api/v1/health")
      .then(setStatus)
      .catch(() => { /* best-effort */ })
  }, [])

  const isSecure = status?.auth_enabled
  const isExposed = status?.network_exposed

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Security</h2>
        <p className="text-sm text-muted-foreground">
          Configure authentication for network-accessible instances
        </p>
      </div>

      {status && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              {isSecure ? (
                <ShieldCheck className="h-4 w-4 text-green-500" />
              ) : (
                <ShieldAlert className="h-4 w-4 text-amber-500" />
              )}
              Current Status
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Badge variant={isSecure ? "default" : "destructive"}>
              {isSecure ? "Authentication enabled" : "No authentication"}
            </Badge>
            <Badge variant={isExposed ? "secondary" : "outline"}>
              {isExposed ? "Network accessible" : "Localhost only"}
            </Badge>
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
