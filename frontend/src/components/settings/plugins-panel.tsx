import { useCallback, useEffect, useState } from "react"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import {
  AlertCircle,
  Brain,
  ChevronDown,
  Download,
  Eye,
  FileEdit,
  FolderSearch,
  Gauge,
  GitBranch,
  Loader2,
  MessageSquare,
  Microscope,
  Network,
  Puzzle,
  Search,
  Settings,
  Stethoscope,
  Tags,
  Terminal,
  Trash2,
  Wand2,
  ExternalLink,
} from "lucide-react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { McpSettingsDialog } from "./mcp-settings-dialog"

// Map icon names from plugin.yaml to lucide components
const ICON_MAP: Record<string, React.ElementType> = {
  search: Search,
  download: Download,
  network: Network,
  brain: Brain,
  tags: Tags,
  "file-edit": FileEdit,
  puzzle: Puzzle,
  "message-square": MessageSquare,
  eye: Eye,
  microscope: Microscope,
  "wand-2": Wand2,
  stethoscope: Stethoscope,
  gauge: Gauge,
  "folder-search": FolderSearch,
  terminal: Terminal,
  "toggle-right": Settings,
}

function getIcon(name: string): React.ElementType {
  return ICON_MAP[name] || Puzzle
}

// Category display order and labels
const CATEGORY_ORDER = ["core", "search", "ai", "visualization", "integration", "export", "mcp", "advanced", "other"]
const CATEGORY_LABELS: Record<string, string> = {
  core: "Core",
  search: "Search & Discovery",
  ai: "AI & Planning",
  visualization: "Visualization",
  integration: "Integrations",
  export: "Export",
  mcp: "MCP Tools",
  advanced: "Advanced",
  other: "Other",
}

interface PluginEndpoint {
  method: string
  path: string
  description: string
}

interface ConfigFieldSchema {
  type: string
  default: unknown
  label?: string
  description?: string
  min?: number
  max?: number
}

interface PluginInfo {
  name: string
  display_name: string
  description: string
  version: string
  author: string
  icon: string
  category: string
  feature_flag: string
  enabled: boolean
  source: string
  error: string | null
  endpoints: PluginEndpoint[]
  config_schema: Record<string, ConfigFieldSchema>
  config: Record<string, unknown>
  requires: string[]
  has_manifest: boolean
}

interface CoreFeature {
  name: string
  display_name: string
  description: string
  icon: string
  category: string
  feature_flag: string
  enabled: boolean
}

// -- Plugin Config Dialog (auto-generated from schema) --

function PluginConfigDialog({
  plugin,
  open,
  onOpenChange,
  onSaved,
}: {
  plugin: PluginInfo
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}) {
  const [config, setConfig] = useState<Record<string, unknown>>(plugin.config || {})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setConfig(plugin.config || {})
  }, [plugin.config])

  const schema = plugin.config_schema || {}
  const fields = Object.entries(schema).filter(([, v]) => v && typeof v === "object" && v.type)

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put(`/api/settings/plugins/${plugin.name}`, config)
      toast.success(`${plugin.display_name} config saved`)
      onSaved()
      onOpenChange(false)
    } catch (err) {
      toast.error(`Failed to save: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  const updateField = (key: string, value: unknown) => {
    setConfig((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{plugin.display_name} Settings</DialogTitle>
          {plugin.description && (
            <DialogDescription>{plugin.description}</DialogDescription>
          )}
        </DialogHeader>

        <div className="py-4 space-y-4">
          {fields.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No configuration options available.
            </p>
          ) : (
            fields.map(([key, field]) => {
              const value = config[key] ?? field.default
              if (field.type === "boolean") {
                return (
                  <div key={key} className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor={key}>{field.label || key}</Label>
                      {field.description && (
                        <p className="text-xs text-muted-foreground">{field.description}</p>
                      )}
                    </div>
                    <Switch
                      id={key}
                      checked={value as boolean}
                      onCheckedChange={(checked) => updateField(key, checked)}
                    />
                  </div>
                )
              }
              if (field.type === "integer" || field.type === "number") {
                return (
                  <div key={key} className="space-y-2">
                    <Label htmlFor={key}>{field.label || key}</Label>
                    <Input
                      id={key}
                      type="number"
                      value={value as number}
                      min={field.min}
                      max={field.max}
                      onChange={(e) => updateField(key, parseInt(e.target.value))}
                    />
                    {field.description && (
                      <p className="text-xs text-muted-foreground">{field.description}</p>
                    )}
                  </div>
                )
              }
              // Default: string
              return (
                <div key={key} className="space-y-2">
                  <Label htmlFor={key}>{field.label || key}</Label>
                  <Input
                    id={key}
                    value={value as string}
                    onChange={(e) => updateField(key, e.target.value)}
                  />
                  {field.description && (
                    <p className="text-xs text-muted-foreground">{field.description}</p>
                  )}
                </div>
              )
            })
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// -- Plugin Card --

function PluginCard({
  plugin,
  onToggle,
  onConfigure,
  onUninstall,
}: {
  plugin: PluginInfo
  onToggle: (flag: string, enabled: boolean) => Promise<void>
  onConfigure: (plugin: PluginInfo) => void
  onUninstall?: (name: string) => void
}) {
  const Icon = getIcon(plugin.icon)
  const hasConfig = plugin.config_schema && Object.keys(plugin.config_schema).some(
    (k) => plugin.config_schema[k]?.type,
  )
  const [endpointsOpen, setEndpointsOpen] = useState(false)

  return (
    <div className="flex items-start gap-3 py-3">
      <div className="mt-0.5">
        <Icon className={`h-4 w-4 ${plugin.enabled ? "text-primary" : "text-muted-foreground"}`} />
      </div>
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium leading-none">{plugin.display_name}</span>
          {plugin.version && (
            <span className="text-xs text-muted-foreground">v{plugin.version}</span>
          )}
          {plugin.source === "external" && (
            <Badge variant="outline" className="text-xs h-4 px-1">
              <ExternalLink className="h-2.5 w-2.5 mr-0.5" />
              external
            </Badge>
          )}
          {plugin.error && (
            <Tooltip>
              <TooltipTrigger>
                <AlertCircle className="h-3.5 w-3.5 text-destructive" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p className="text-xs">Import error: {plugin.error}</p>
              </TooltipContent>
            </Tooltip>
          )}
        </div>
        {plugin.description && (
          <p className="text-sm text-muted-foreground">{plugin.description}</p>
        )}
        {plugin.endpoints.length > 0 && (
          <Collapsible open={endpointsOpen} onOpenChange={setEndpointsOpen}>
            <CollapsibleTrigger asChild>
              <button className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mt-1">
                <ChevronDown className={`h-3 w-3 transition-transform ${endpointsOpen ? "rotate-0" : "-rotate-90"}`} />
                {plugin.endpoints.length} endpoint{plugin.endpoints.length !== 1 ? "s" : ""}
                {plugin.author && <span className="ml-1">by {plugin.author}</span>}
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="mt-2 space-y-0.5 text-xs font-mono text-muted-foreground bg-muted/50 rounded p-2">
                {plugin.endpoints.map((ep, i) => (
                  <div key={i} className="flex gap-2">
                    <span className={`font-semibold w-14 text-right ${
                      ep.method === "GET" ? "text-green-600 dark:text-green-400" :
                      ep.method === "POST" ? "text-blue-600 dark:text-blue-400" :
                      ep.method === "DELETE" ? "text-red-600 dark:text-red-400" :
                      ep.method === "PUT" ? "text-amber-600 dark:text-amber-400" :
                      ""
                    }`}>{ep.method}</span>
                    <span className="flex-1">{ep.path}</span>
                  </div>
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        {hasConfig && plugin.enabled && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => onConfigure(plugin)}
            aria-label={`Configure ${plugin.display_name}`}
          >
            <Settings className="h-3.5 w-3.5" />
          </Button>
        )}
        {plugin.source === "external" && onUninstall && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-destructive hover:text-destructive"
            onClick={() => onUninstall(plugin.name)}
            aria-label={`Uninstall ${plugin.display_name}`}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
        <Switch
          checked={plugin.enabled}
          onCheckedChange={(checked) => onToggle(plugin.feature_flag, checked)}
          className="mt-0.5"
          disabled={!!plugin.error}
        />
      </div>
    </div>
  )
}

// -- Core Feature Toggle --

function CoreFeatureToggle({
  feature,
  onToggle,
  onOpenMcpSettings,
}: {
  feature: CoreFeature
  onToggle: (flag: string, enabled: boolean) => Promise<void>
  onOpenMcpSettings?: (toolName: string, label: string) => void
}) {
  const Icon = getIcon(feature.icon)
  const isMcp = feature.category === "mcp"

  return (
    <div className="flex items-start justify-between py-3 gap-4">
      <div className="flex items-start gap-3 flex-1">
        <div className="mt-0.5">
          <Icon className="h-4 w-4 text-muted-foreground" />
        </div>
        <div className="space-y-1 flex-1">
          <div className="text-sm font-medium leading-none">{feature.display_name}</div>
          {feature.description && (
            <div className="text-sm text-muted-foreground">{feature.description}</div>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {isMcp && onOpenMcpSettings && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => onOpenMcpSettings(feature.name.replace("mcp_", ""), feature.display_name)}
            aria-label={`Configure ${feature.display_name}`}
          >
            <Settings className="h-3.5 w-3.5" />
          </Button>
        )}
        <Switch
          checked={feature.enabled}
          onCheckedChange={(checked) => onToggle(feature.feature_flag, checked)}
          className="mt-0.5"
        />
      </div>
    </div>
  )
}

// -- Install Plugin Dialog --

function InstallPluginDialog({
  open,
  onOpenChange,
  onInstalled,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onInstalled: () => void
}) {
  const [url, setUrl] = useState("")
  const [installing, setInstalling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleInstall = async () => {
    if (!url.trim()) return
    setInstalling(true)
    setError(null)
    try {
      const res = await api.post<{ name: string; message: string }>("/api/plugins/install", { url: url.trim() })
      toast.success(res.message || `Plugin '${res.name}' installed`)
      setUrl("")
      onInstalled()
      onOpenChange(false)
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Install failed: ${msg}`)
    } finally {
      setInstalling(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Install Plugin from GitHub</DialogTitle>
          <DialogDescription>
            Point to a GitHub repository containing an mdkb plugin.
            The plugin must have an __init__.py with FEATURE_FLAG and router exports.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="plugin-url">GitHub URL</Label>
            <Input
              id="plugin-url"
              value={url}
              onChange={(e) => { setUrl(e.target.value); setError(null) }}
              placeholder="https://github.com/user/repo or user/repo/tree/main/path"
              onKeyDown={(e) => e.key === "Enter" && handleInstall()}
            />
            {error && (
              <p className="text-xs text-destructive flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {error}
              </p>
            )}
          </div>
          <div className="text-xs text-muted-foreground space-y-1">
            <p className="font-medium">Supported URL formats:</p>
            <ul className="list-disc list-inside space-y-0.5 ml-1">
              <li><code className="text-xs">https://github.com/user/repo</code> — entire repo as plugin</li>
              <li><code className="text-xs">https://github.com/user/repo/tree/main/path/to/plugin</code> — subdirectory</li>
              <li><code className="text-xs">user/repo</code> — shorthand for github.com</li>
            </ul>
          </div>
          <div className="bg-muted/50 rounded-md p-3 text-xs text-muted-foreground space-y-1.5">
            <p className="font-medium text-foreground">Plugin requirements:</p>
            <ul className="list-disc list-inside space-y-0.5 ml-1">
              <li>__init__.py with <code>FEATURE_FLAG</code> and <code>router</code></li>
              <li>plugin.yaml manifest (recommended)</li>
              <li>requirements.txt for dependencies (optional)</li>
            </ul>
            <p className="mt-2">
              After installing, enable the feature flag and restart the container to activate.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleInstall} disabled={installing || !url.trim()}>
            {installing ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                Installing...
              </>
            ) : (
              <>
                <Download className="h-3.5 w-3.5 mr-1.5" />
                Install
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// -- Main Panel --

export function PluginsPanel({
  features,
  mcpConfig,
  onToggle,
}: {
  features: Record<string, boolean>
  mcpConfig?: Record<string, unknown>
  onToggle: (name: string, enabled: boolean) => Promise<void>
}) {
  const [plugins, setPlugins] = useState<PluginInfo[]>([])
  const [coreFeatures, setCoreFeatures] = useState<CoreFeature[]>([])
  const [loading, setLoading] = useState(true)
  const [configPlugin, setConfigPlugin] = useState<PluginInfo | null>(null)
  const [installOpen, setInstallOpen] = useState(false)
  const [mcpDialog, setMcpDialog] = useState<{
    open: boolean; toolName: string; toolLabel: string
  } | null>(null)

  const loadPlugins = useCallback(async () => {
    try {
      const res = await api.get<{ plugins: PluginInfo[]; core_features: CoreFeature[] }>("/api/plugins")
      setPlugins(res.plugins)
      setCoreFeatures(res.core_features)
    } catch {
      // Fallback: show features as flat toggles
      setCoreFeatures(
        Object.entries(features).map(([name, enabled]) => ({
          name,
          display_name: name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
          description: "",
          icon: "toggle-right",
          category: "other",
          feature_flag: name,
          enabled,
        }))
      )
    } finally {
      setLoading(false)
    }
  }, [features])

  useEffect(() => {
    loadPlugins()
  }, [loadPlugins])

  // Sync enabled state from features prop (after toggle)
  useEffect(() => {
    setPlugins((prev) =>
      prev.map((p) => ({
        ...p,
        enabled: p.feature_flag ? (features[p.feature_flag] ?? p.enabled) : p.enabled,
      }))
    )
    setCoreFeatures((prev) =>
      prev.map((f) => ({
        ...f,
        enabled: features[f.feature_flag] ?? f.enabled,
      }))
    )
  }, [features])

  const handleUninstall = async (name: string) => {
    if (!confirm(`Uninstall plugin '${name}'? This cannot be undone.`)) return
    try {
      await api.del(`/api/plugins/${name}`)
      toast.success(`Plugin '${name}' uninstalled. Restart to complete cleanup.`)
      loadPlugins()
    } catch (err) {
      toast.error(`Failed to uninstall: ${(err as Error).message}`)
    }
  }

  // Group plugins by category
  const pluginsByCategory = plugins.reduce<Record<string, PluginInfo[]>>((acc, p) => {
    const cat = p.category || "other"
    ;(acc[cat] ||= []).push(p)
    return acc
  }, {})

  // Group core features by category
  const coreByCategory = coreFeatures.reduce<Record<string, CoreFeature[]>>((acc, f) => {
    const cat = f.category || "other"
    ;(acc[cat] ||= []).push(f)
    return acc
  }, {})

  // Merged category list (sorted)
  const allCategories = [...new Set([
    ...Object.keys(pluginsByCategory),
    ...Object.keys(coreByCategory),
  ])].sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a)
    const bi = CATEGORY_ORDER.indexOf(b)
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
  })

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-8 justify-center text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">Loading plugins...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {allCategories.map((category) => {
        const catPlugins = pluginsByCategory[category] || []
        const catCore = coreByCategory[category] || []
        if (catPlugins.length === 0 && catCore.length === 0) return null

        return (
          <Card key={category}>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">{CATEGORY_LABELS[category] || category}</CardTitle>
              {category === "core" && (
                <CardDescription>Essential functionality for your knowledge base</CardDescription>
              )}
              {category === "mcp" && (
                <CardDescription>Model Context Protocol tool integrations</CardDescription>
              )}
            </CardHeader>
            <CardContent className="space-y-0">
              {catCore.map((feature, idx) => (
                <div key={feature.name}>
                  <CoreFeatureToggle
                    feature={feature}
                    onToggle={onToggle}
                    onOpenMcpSettings={
                      feature.category === "mcp"
                        ? (toolName, label) => setMcpDialog({ open: true, toolName, toolLabel: label })
                        : undefined
                    }
                  />
                  {(idx < catCore.length - 1 || catPlugins.length > 0) && <Separator />}
                </div>
              ))}
              {catPlugins.map((plugin, idx) => (
                <div key={plugin.name}>
                  <PluginCard
                    plugin={plugin}
                    onToggle={onToggle}
                    onConfigure={setConfigPlugin}
                    onUninstall={plugin.source === "external" ? handleUninstall : undefined}
                  />
                  {idx < catPlugins.length - 1 && <Separator />}
                </div>
              ))}
            </CardContent>
          </Card>
        )
      })}

      {/* Install Plugin */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <GitBranch className="h-4 w-4" />
            Install Plugin
          </CardTitle>
          <CardDescription>
            Add plugins from GitHub repositories to extend mdkb
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="outline"
            onClick={() => setInstallOpen(true)}
            className="w-full"
          >
            <Download className="h-4 w-4 mr-2" />
            Install from GitHub
          </Button>
        </CardContent>
      </Card>

      {/* Config Dialog (auto-generated from manifest schema) */}
      {configPlugin && (
        <PluginConfigDialog
          plugin={configPlugin}
          open={!!configPlugin}
          onOpenChange={(open) => !open && setConfigPlugin(null)}
          onSaved={loadPlugins}
        />
      )}

      {/* Install Dialog */}
      <InstallPluginDialog
        open={installOpen}
        onOpenChange={setInstallOpen}
        onInstalled={loadPlugins}
      />

      {/* MCP Settings Dialog (existing) */}
      {mcpDialog && (
        <McpSettingsDialog
          toolName={mcpDialog.toolName}
          toolLabel={mcpDialog.toolLabel}
          config={(mcpConfig?.[mcpDialog.toolName] as Record<string, unknown>) || {}}
          open={mcpDialog.open}
          onOpenChange={(open) => !open && setMcpDialog(null)}
          onSave={() => setMcpDialog(null)}
        />
      )}
    </div>
  )
}
