import { useState } from "react"
import { LogViewer } from "./log-viewer"
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
import {
  useMcpPanel,
  FLAG_DEFS,
  type McpInfo,
  type McpTool,
} from "@/hooks/use-mcp-panel"

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
  } else {
    lines.push("# No authentication (localhost only)")
  }
  return lines.join("\n")
}

// -- Tool row ---------------------------------------------------------------

interface ToolRowProps {
  tool: McpTool
}

function ToolRow({ tool }: ToolRowProps) {
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

export interface McpPanelProps {
  onToggleMcpFlag: (name: string, enabled: boolean) => Promise<void>
}

export function McpPanel({ onToggleMcpFlag }: McpPanelProps) {
  const {
    info,
    toolsResp,
    loading,
    testing,
    testResult,
    newHost,
    setNewHost,
    savingHosts,
    newOrigin,
    setNewOrigin,
    savingOrigins,
    rateLimit,
    setRateLimit,
    savingRateLimit,
    mcpLogLevel,
    toolsByCategory,
    handleMcpLogLevel,
    handleToggleFlag,
    handleTestConnection,
    handleAddHost,
    handleRemoveHost,
    handleAddOrigin,
    handleRemoveOrigin,
    handleSaveRateLimit,
  } = useMcpPanel({ onToggleMcpFlag })

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
      <ConnectionCard
        info={info}
        testing={testing}
        testResult={testResult}
        onTestConnection={handleTestConnection}
      />

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
      <AllowedListCard
        title="Allowed hosts"
        description="DNS rebinding protection for the Streamable HTTP transport. Add the hostname MCP clients use to reach this server. Restart the MCP server to apply changes."
        items={info.allowed_hosts}
        emptyLabel="No hosts configured."
        inputPlaceholder="host.docker.internal:* or mcp.example.com"
        inputValue={newHost}
        onInputChange={setNewHost}
        onAdd={handleAddHost}
        onRemove={handleRemoveHost}
        saving={savingHosts}
      />

      {/* Allowed origins */}
      <AllowedListCard
        title="Allowed origins"
        description={
          <>
            Controls which browser origins (the <code>Origin</code> header) can connect.
            Use <code>*</code> to allow all, or <code>http://hostname:*</code> for a wildcard port
            match. Restart the MCP server to apply changes.
          </>
        }
        items={info.allowed_origins}
        emptyLabel="No origins configured — all cross-origin requests will be rejected."
        inputPlaceholder="* or http://your-server.local:*"
        inputValue={newOrigin}
        onInputChange={setNewOrigin}
        onAdd={handleAddOrigin}
        onRemove={handleRemoveOrigin}
        saving={savingOrigins}
      />

      {/* Rate limit */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Rate limit</CardTitle>
          <CardDescription>
            Cap requests per minute per API key (or per remote IP if no key is configured).
            Protects against runaway clients and LLM-cost abuse. <code>0</code> disables it.
            Restart the MCP server to apply changes.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 items-center">
            <Input
              type="number"
              min={0}
              max={100000}
              value={rateLimit}
              onChange={(e) => setRateLimit(e.target.value)}
              className="h-8 text-xs w-32"
            />
            <span className="text-xs text-muted-foreground">requests / minute</span>
            <Button
              variant="outline"
              size="sm"
              onClick={handleSaveRateLimit}
              disabled={savingRateLimit || rateLimit === String(info.rate_limit_per_minute ?? 0)}
            >
              {savingRateLimit ? "Saving\u2026" : "Save"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* MCP server logs */}
      <LogViewer
        logsUrl="/api/v1/mcp/logs"
        title="MCP Server Logs"
        description="Live log output from the MCP server process. Restart MCP server to reconnect."
        logLevel={mcpLogLevel}
        onLogLevelChange={handleMcpLogLevel}
        pollInterval={5000}
      />

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

// -- Connection card --------------------------------------------------------

interface ConnectionCardProps {
  info: McpInfo
  testing: boolean
  testResult: "ok" | "fail" | null
  onTestConnection: () => void
}

function ConnectionCard({ info, testing, testResult, onTestConnection }: ConnectionCardProps) {
  return (
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
              <span className="text-xs">{info.auth_methods.join(" \u00b7 ")}</span>
            </>
          )}
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onTestConnection}
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
  )
}

// -- Allowed list card (hosts / origins) ------------------------------------

interface AllowedListCardProps {
  title: string
  description: React.ReactNode
  items: string[]
  emptyLabel: string
  inputPlaceholder: string
  inputValue: string
  onInputChange: (value: string) => void
  onAdd: () => void
  onRemove: (item: string) => void
  saving: boolean
}

function AllowedListCard({
  title,
  description,
  items,
  emptyLabel,
  inputPlaceholder,
  inputValue,
  onInputChange,
  onAdd,
  onRemove,
  saving,
}: AllowedListCardProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.length === 0 ? (
          <div className="text-xs text-muted-foreground italic">{emptyLabel}</div>
        ) : (
          <div className="space-y-1">
            {items.map((item) => (
              <div
                key={item}
                className="flex items-center justify-between gap-2 rounded border bg-muted/30 px-2 py-1"
              >
                <span className="text-xs font-mono break-all">{item}</span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 text-destructive hover:text-destructive"
                  onClick={() => onRemove(item)}
                  disabled={saving}
                  aria-label={`Remove ${item}`}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <Input
            placeholder={inputPlaceholder}
            value={inputValue}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                onAdd()
              }
            }}
            className="h-8 text-xs"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={onAdd}
            disabled={saving || !inputValue.trim()}
          >
            <Plus className="h-3 w-3 mr-1" />
            Add
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
