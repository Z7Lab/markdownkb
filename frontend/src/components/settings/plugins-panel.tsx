import { useCallback, useEffect, useState } from "react"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
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
import { PluginConfigDialog } from "./plugin-config-dialog"
import { InstallPluginDialog } from "./install-plugin-dialog"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import type { PluginInfo, CoreFeature } from "./plugin-types"

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

// -- Plugin Card --

function PluginCard({
  plugin,
  onToggle,
  onConfigure,
  onUninstall,
}: {
  plugin: PluginInfo
  onToggle: (name: string, enabled: boolean) => Promise<void>
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
        {plugin.system_dependencies?.length > 0 && !plugin.dependencies_met && (
          <div className="text-xs space-y-1 mt-1 p-2 rounded border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30">
            <p className="font-medium text-amber-800 dark:text-amber-200">Missing system dependencies:</p>
            {plugin.system_dependencies.filter((d) => !d.available).map((d) => (
              <div key={d.binary} className="text-amber-700 dark:text-amber-300">
                <span className="font-mono">{d.binary}</span>
                {!d.required && <span className="text-amber-600 dark:text-amber-400"> (optional)</span>}
                {d.install_hint && <span className="text-amber-600 dark:text-amber-400"> — {d.install_hint}</span>}
              </div>
            ))}
          </div>
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
          onCheckedChange={(checked) => onToggle(plugin.name, checked)}
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
  onToggle: (name: string, enabled: boolean) => Promise<void>
  onOpenMcpSettings?: (toolName: string, label: string) => void
}) {
  const Icon = getIcon(feature.icon)
  const isMcp = feature.section === "mcp"

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
            onClick={() => onOpenMcpSettings(feature.name, feature.display_name)}
            aria-label={`Configure ${feature.display_name}`}
          >
            <Settings className="h-3.5 w-3.5" />
          </Button>
        )}
        <Switch
          checked={feature.enabled}
          onCheckedChange={(checked) => onToggle(feature.name, checked)}
          className="mt-0.5"
        />
      </div>
    </div>
  )
}

// -- Main Panel --

export function PluginsPanel({
  mcpConfig,
  onToggleCore,
  onToggleMcpFlag,
  onTogglePlugin,
}: {
  mcpConfig?: Record<string, unknown>
  onToggleCore: (name: string, enabled: boolean) => Promise<void>
  onToggleMcpFlag: (name: string, enabled: boolean) => Promise<void>
  onTogglePlugin: (name: string, enabled: boolean) => Promise<void>
}) {
  const [plugins, setPlugins] = useState<PluginInfo[]>([])
  const [coreFeatures, setCoreFeatures] = useState<CoreFeature[]>([])
  const [loading, setLoading] = useState(true)
  const [configPlugin, setConfigPlugin] = useState<PluginInfo | null>(null)
  const [installOpen, setInstallOpen] = useState(false)
  const [mcpDialog, setMcpDialog] = useState<{
    open: boolean; toolName: string; toolLabel: string
  } | null>(null)
  const [pendingUninstall, setPendingUninstall] = useState<string | null>(null)

  const loadPlugins = useCallback(async () => {
    try {
      const res = await api.get<{ plugins: PluginInfo[]; core_features: CoreFeature[] }>("/api/plugins")
      setPlugins(res.plugins)
      setCoreFeatures(res.core_features)
    } catch (err) {
      console.warn("Failed to load plugins:", (err as Error).message)
      toast.warning("Could not load plugin details")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPlugins()
  }, [loadPlugins])

  const handleUninstall = async (name: string) => {
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
                    onToggle={async (name, enabled) => {
                      if (feature.section === "mcp") {
                        await onToggleMcpFlag(name, enabled)
                      } else {
                        await onToggleCore(name, enabled)
                      }
                      loadPlugins()
                    }}
                    onOpenMcpSettings={
                      feature.section === "mcp"
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
                    onToggle={async (name, enabled) => {
                      await onTogglePlugin(name, enabled)
                      loadPlugins()
                    }}
                    onConfigure={setConfigPlugin}
                    onUninstall={plugin.source === "external" ? setPendingUninstall : undefined}
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
            Add plugins from GitHub repositories or local directories
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="outline"
            onClick={() => setInstallOpen(true)}
            className="w-full"
          >
            <Download className="h-4 w-4 mr-2" />
            Install Plugin
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

      {/* Uninstall confirmation dialog */}
      <ConfirmDialog
        open={!!pendingUninstall}
        onOpenChange={(open) => { if (!open) setPendingUninstall(null) }}
        title="Uninstall plugin?"
        description={`Uninstall plugin '${pendingUninstall}'? This cannot be undone.`}
        confirmLabel="Uninstall"
        variant="destructive"
        onConfirm={async () => {
          if (pendingUninstall) {
            const name = pendingUninstall
            setPendingUninstall(null)
            await handleUninstall(name)
          }
        }}
      />
    </div>
  )
}
