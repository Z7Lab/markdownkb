import { useCallback, useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { CodeBlock } from "@/components/ui/code-block"
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  Loader2,
  Lock,
  Plug,
  Plus,
  Trash2,
  Wrench,
  XCircle,
} from "lucide-react"
import { api } from "@/lib/api"
import { toast } from "sonner"

// -- Types matching GET /api/mcp/info and GET /api/mcp/tools ----------------

type McpFlagKey = "read_only" | "allow_bucket_writes" | "save_document" | "track_history"

type McpInfo = {
  endpoint: string
  transport: string
  auth_enabled: boolean
  auth_methods: string[]
  flags: Record<string, boolean>
  allowed_hosts: string[]
}

type McpToolParam = {
  name: string
  type: string
  required: boolean
  default: string | null
}

type McpTool = {
  name: string
  description: string
  write: boolean
  requires_plugin: string | null
  feature_flag: string | null
  enabled: boolean
  disabled_reason: string | null
  parameters: McpToolParam[]
}

type McpToolsResponse = {
  tools: McpTool[]
  total: number
  enabled: number
  import_errors: { module: string; error: string }[]
}

// -- Flag metadata ----------------------------------------------------------

const FLAG_DEFS: { key: McpFlagKey; label: string; description: string }[] = [
  {
    key: "read_only",
    label: "Read-only",
    description:
      "Disable all write tools (save_file, delete_file, index_file). Overridden for bucket tools by Allow bucket writes.",
  },
  {
    key: "allow_bucket_writes",
    label: "Allow bucket writes",
    description:
      "Exempt bucket_create/add/push/delete from read-only mode. Buckets are isolated from the main index.",
  },
  {
    key: "save_document",
    label: "Save document tool",
    description: "Enable the save_file MCP tool for writing markdown into configured sources.",
  },
  {
    key: "track_history",
    label: "Track history",
    description: "Record MCP search and chat calls to the web UI history sidebar.",
  },
]

// -- Connection config snippets ---------------------------------------------

function claudeDesktopConfig(endpoint: string, authEnabled: boolean): string {
  const config: Record<string, unknown> = {
    mcpServers: {
      markdownkb: {
        url: endpoint,
        transport: "streamable-http",
        ...(authEnabled
          ? { headers: { Authorization: "Bearer YOUR_API_KEY" } }
          : {}),
      },
    },
  }
  return JSON.stringify(config, null, 2)
}

function genericConfig(endpoint: string, authEnabled: boolean): string {
  const lines = [
    `# Streamable HTTP endpoint`,
    endpoint,
    "",
  ]
  if (authEnabled) {
    lines.push("# Authentication (send one of these):")
    lines.push("Authorization: Bearer YOUR_API_KEY")
    lines.push("X-MarkdownKB-Key: YOUR_API_KEY")
    lines.push("?token=YOUR_API_KEY  (query param, legacy)")
  } else {
    lines.push("# No authentication (localhost only)")
  }
  return lines.join("\n")
}

// -- Tool row ---------------------------------------------------------------

function ToolRow({ tool }: { tool: McpTool }) {
  const [open, setOpen] = useState(false)
  const hasParams = tool.parameters.length > 0

  return (
    <div className="py-2.5">
      <div className="flex items-start gap-3">
        <div className="mt-1">
          {tool.enabled ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-500" />
          ) : (
            <XCircle className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-sm font-mono font-medium ${tool.enabled ? "" : "text-muted-foreground"}`}>
              {tool.name}
            </span>
            {tool.write && (
              <Badge variant="outline" className="text-xs h-4 px-1">write</Badge>
            )}
            {tool.requires_plugin && (
              <Badge variant="outline" className="text-xs h-4 px-1">
                plugin: {tool.requires_plugin}
              </Badge>
            )}
            {tool.feature_flag && (
              <Badge variant="outline" className="text-xs h-4 px-1">
                flag: {tool.feature_flag}
              </Badge>
            )}
          </div>
          {tool.description && (
            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{tool.description}</p>
          )}
          {!tool.enabled && tool.disabled_reason && (
            <p className="text-xs text-amber-700 dark:text-amber-400 mt-1">
              Disabled: {tool.disabled_reason}
            </p>
          )}
          {hasParams && (
            <Collapsible open={open} onOpenChange={setOpen}>
              <CollapsibleTrigger asChild>
                <button className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mt-1">
                  <ChevronDown
                    className={`h-3 w-3 transition-transform ${open ? "rotate-0" : "-rotate-90"}`}
                  />
                  {tool.parameters.length} parameter{tool.parameters.length !== 1 ? "s" : ""}
                </button>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="mt-2 space-y-1 text-xs font-mono bg-muted/50 rounded p-2">
                  {tool.parameters.map((p) => (
                    <div key={p.name} className="flex gap-2">
                      <span className="font-semibold">{p.name}</span>
                      <span className="text-muted-foreground">{p.type}</span>
                      {p.required ? (
                        <span className="text-amber-700 dark:text-amber-400">required</span>
                      ) : (
                        <span className="text-muted-foreground">
                          = {p.default ?? "None"}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </CollapsibleContent>
            </Collapsible>
          )}
        </div>
      </div>
    </div>
  )
}

// -- Main panel -------------------------------------------------------------

export function McpPanel({
  onToggleMcpFlag,
}: {
  onToggleMcpFlag: (name: string, enabled: boolean) => Promise<void>
}) {
  const [info, setInfo] = useState<McpInfo | null>(null)
  const [toolsResp, setToolsResp] = useState<McpToolsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<"ok" | "fail" | null>(null)
  const [newHost, setNewHost] = useState("")
  const [savingHosts, setSavingHosts] = useState(false)

  const load = useCallback(async () => {
    try {
      const [infoRes, toolsRes] = await Promise.all([
        api.get<McpInfo>("/api/mcp/info"),
        api.get<McpToolsResponse>("/api/mcp/tools"),
      ])
      setInfo(infoRes)
      setToolsResp(toolsRes)
    } catch (err) {
      toast.error(`Failed to load MCP info: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleToggleFlag = useCallback(
    async (name: string, enabled: boolean) => {
      await onToggleMcpFlag(name, enabled)
      await load()
    },
    [onToggleMcpFlag, load],
  )

  const handleTestConnection = useCallback(async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await api.get<McpToolsResponse>("/api/mcp/tools")
      setTestResult("ok")
      toast.success(`MCP ready — ${res.enabled} of ${res.total} tools active`)
    } catch (err) {
      setTestResult("fail")
      toast.error(`MCP unreachable: ${(err as Error).message}`)
    } finally {
      setTesting(false)
    }
  }, [])

  const handleAddHost = useCallback(async () => {
    if (!info || !newHost.trim()) return
    const next = [...info.allowed_hosts, newHost.trim()]
    setSavingHosts(true)
    try {
      await api.put("/api/mcp/allowed-hosts", { allowed_hosts: next })
      setNewHost("")
      await load()
      toast.success("Allowed hosts updated. Restart MCP server to apply.")
    } catch (err) {
      toast.error(`Failed to save: ${(err as Error).message}`)
    } finally {
      setSavingHosts(false)
    }
  }, [info, newHost, load])

  const handleRemoveHost = useCallback(
    async (host: string) => {
      if (!info) return
      const next = info.allowed_hosts.filter((h) => h !== host)
      setSavingHosts(true)
      try {
        await api.put("/api/mcp/allowed-hosts", { allowed_hosts: next })
        await load()
      } catch (err) {
        toast.error(`Failed to save: ${(err as Error).message}`)
      } finally {
        setSavingHosts(false)
      }
    },
    [info, load],
  )

  const toolsByCategory = useMemo(() => {
    if (!toolsResp) return { enabled: [], disabled: [] }
    return {
      enabled: toolsResp.tools.filter((t) => t.enabled),
      disabled: toolsResp.tools.filter((t) => !t.enabled),
    }
  }, [toolsResp])

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-8 justify-center text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">Loading MCP info...</span>
      </div>
    )
  }

  if (!info || !toolsResp) {
    return (
      <div className="text-sm text-muted-foreground">Failed to load MCP information.</div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Connection */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Plug className="h-4 w-4" />
            Connection
          </CardTitle>
          <CardDescription>
            Streamable HTTP endpoint for MCP clients (Claude Desktop, Claude Code, custom agents).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <span className="text-muted-foreground">Endpoint</span>
            <span className="font-mono text-xs break-all">{info.endpoint}</span>
            <span className="text-muted-foreground">Transport</span>
            <span className="font-mono text-xs">{info.transport}</span>
            <span className="text-muted-foreground">Authentication</span>
            <span className="flex items-center gap-2 text-xs">
              {info.auth_enabled ? (
                <>
                  <Lock className="h-3 w-3" />
                  <span>Required</span>
                </>
              ) : (
                <span className="text-muted-foreground">Disabled (localhost only)</span>
              )}
            </span>
            {info.auth_enabled && (
              <>
                <span className="text-muted-foreground">Auth methods</span>
                <span className="text-xs">{info.auth_methods.join(" · ")}</span>
              </>
            )}
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleTestConnection}
              disabled={testing}
            >
              {testing ? (
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              ) : testResult === "ok" ? (
                <CheckCircle2 className="h-3 w-3 mr-1 text-emerald-600" />
              ) : testResult === "fail" ? (
                <AlertCircle className="h-3 w-3 mr-1 text-destructive" />
              ) : null}
              Test connection
            </Button>
          </div>

          <div>
            <div className="text-xs text-muted-foreground mb-1">Claude Desktop (.mcp.json)</div>
            <CodeBlock code={claudeDesktopConfig(info.endpoint, info.auth_enabled)} language="json" />
          </div>
          <div>
            <div className="text-xs text-muted-foreground mb-1">Generic client</div>
            <CodeBlock code={genericConfig(info.endpoint, info.auth_enabled)} language="bash" />
          </div>
        </CardContent>
      </Card>

      {/* Feature flags */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Feature flags</CardTitle>
          <CardDescription>
            Control which MCP capabilities are exposed. Changes apply to newly connected clients.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-0">
          {FLAG_DEFS.map((f, idx) => (
            <div key={f.key}>
              <div className="flex items-start justify-between py-3 gap-4">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">{f.label}</div>
                  <div className="text-xs text-muted-foreground">{f.description}</div>
                </div>
                <Switch
                  checked={!!info.flags[f.key]}
                  onCheckedChange={(checked) => handleToggleFlag(f.key, checked)}
                  className="mt-0.5"
                />
              </div>
              {idx < FLAG_DEFS.length - 1 && <Separator />}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Allowed hosts */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Allowed hosts</CardTitle>
          <CardDescription>
            DNS rebinding protection for the Streamable HTTP transport. Add the hostname MCP clients
            use to reach this server. Restart the MCP server to apply changes.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {info.allowed_hosts.length === 0 ? (
            <div className="text-xs text-muted-foreground italic">No hosts configured.</div>
          ) : (
            <div className="space-y-1">
              {info.allowed_hosts.map((host) => (
                <div
                  key={host}
                  className="flex items-center justify-between gap-2 rounded border bg-muted/30 px-2 py-1"
                >
                  <span className="text-xs font-mono break-all">{host}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 text-destructive hover:text-destructive"
                    onClick={() => handleRemoveHost(host)}
                    disabled={savingHosts}
                    aria-label={`Remove ${host}`}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <Input
              placeholder="host.docker.internal:* or mcp.example.com"
              value={newHost}
              onChange={(e) => setNewHost(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault()
                  handleAddHost()
                }
              }}
              className="h-8 text-xs"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleAddHost}
              disabled={savingHosts || !newHost.trim()}
            >
              <Plus className="h-3 w-3 mr-1" />
              Add
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Tool browser */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Wrench className="h-4 w-4" />
            Tools ({toolsResp.enabled} of {toolsResp.total} enabled)
          </CardTitle>
          <CardDescription>
            All discovered MCP tools. Disabled tools show the reason — usually a plugin or feature
            flag that needs to be enabled.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-0 divide-y">
          {toolsByCategory.enabled.map((t) => (
            <ToolRow key={t.name} tool={t} />
          ))}
          {toolsByCategory.disabled.length > 0 && (
            <div className="pt-3">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide py-2">
                Disabled
              </div>
              <div className="divide-y">
                {toolsByCategory.disabled.map((t) => (
                  <ToolRow key={t.name} tool={t} />
                ))}
              </div>
            </div>
          )}
          {toolsResp.import_errors.length > 0 && (
            <div className="pt-3">
              <div className="text-xs font-semibold text-destructive uppercase tracking-wide py-2">
                Import errors
              </div>
              {toolsResp.import_errors.map((err) => (
                <div key={err.module} className="text-xs font-mono py-1">
                  <span className="text-destructive">{err.module}:</span> {err.error}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
