import { useState } from "react"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { MessageSquare, Eye, FileSearch, Terminal, Brain, Wrench, Activity, Shield, Tag, Settings, Network } from "lucide-react"
import { McpSettingsDialog } from "./mcp-settings-dialog"

type FeatureInfo = {
  label: string
  description: string
  icon: React.ElementType
  category: "core" | "mcp" | "advanced"
}

const FEATURE_METADATA: Record<string, FeatureInfo> = {
  rag_chat: {
    label: "RAG Chat",
    description: "Enable AI chat with retrieval-augmented generation from your knowledge base",
    icon: MessageSquare,
    category: "core",
  },
  file_watcher: {
    label: "File Watcher",
    description: "Automatically detect and index new or modified files in your sources",
    icon: Eye,
    category: "core",
  },
  mcp_filesystem: {
    label: "Filesystem",
    description: "Browse directories and read files through MCP tools",
    icon: FileSearch,
    category: "mcp",
  },
  mcp_terminal: {
    label: "Terminal",
    description: "Execute safe terminal commands via MCP",
    icon: Terminal,
    category: "mcp",
  },
  mcp_tag_generator: {
    label: "Tag Generator",
    description: "AI-powered automatic tag generation for markdown files",
    icon: Tag,
    category: "mcp",
  },
  mcts_planner: {
    label: "MCTS Planner",
    description: "Monte Carlo Tree Search for complex task planning",
    icon: Brain,
    category: "advanced",
  },
  agent_skills: {
    label: "Agent Skills",
    description: "Enable custom skill system for the AI agent",
    icon: Wrench,
    category: "advanced",
  },
  diagnostics: {
    label: "Diagnostics",
    description: "Show detailed diagnostic information in the UI",
    icon: Activity,
    category: "advanced",
  },
  knowledge_graph: {
    label: "Knowledge Graph",
    description: "Interactive 3D visualization of document relationships and topic clusters",
    icon: Network,
    category: "advanced",
  },
  rate_limiting: {
    label: "Rate Limiting",
    description: "Enable API rate limiting for security and resource management",
    icon: Shield,
    category: "advanced",
  },
}

function FeatureToggle({
  name,
  enabled,
  onToggle,
  onOpenSettings,
}: {
  name: string
  enabled: boolean
  onToggle: (name: string, enabled: boolean) => Promise<void>
  onOpenSettings?: () => void
}) {
  const info = FEATURE_METADATA[name]
  const isMcpTool = info?.category === "mcp"

  if (!info) {
    // Fallback for unknown features
    return (
      <div className="flex items-center justify-between py-3">
        <div className="space-y-0.5 flex-1">
          <div className="text-sm font-medium">{name}</div>
        </div>
        <Switch checked={enabled} onCheckedChange={(checked) => onToggle(name, checked)} />
      </div>
    )
  }

  const Icon = info.icon

  return (
    <div className="flex items-start justify-between py-3 gap-4">
      <div className="flex items-start gap-3 flex-1">
        <div className="mt-0.5">
          <Icon className="h-4 w-4 text-muted-foreground" />
        </div>
        <div className="space-y-1 flex-1">
          <div className="text-sm font-medium leading-none">{info.label}</div>
          <div className="text-sm text-muted-foreground">{info.description}</div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {isMcpTool && onOpenSettings && (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onOpenSettings}
            aria-label={`Configure ${info.label}`}
          >
            <Settings className="h-4 w-4" />
          </Button>
        )}
        <Switch
          checked={enabled}
          onCheckedChange={(checked) => onToggle(name, checked)}
          className="mt-0.5"
        />
      </div>
    </div>
  )
}

export function FeaturesPanel({
  features,
  mcpConfig,
  onToggle,
}: {
  features: Record<string, boolean>
  mcpConfig?: Record<string, unknown>
  onToggle: (name: string, enabled: boolean) => Promise<void>
}) {
  const [settingsDialog, setSettingsDialog] = useState<{
    open: boolean
    toolName: string
    toolLabel: string
  } | null>(null)

  // Group features by category
  const coreFeatures = Object.entries(features).filter(
    ([name]) => FEATURE_METADATA[name]?.category === "core"
  )
  const mcpFeatures = Object.entries(features).filter(
    ([name]) => FEATURE_METADATA[name]?.category === "mcp"
  )
  const advancedFeatures = Object.entries(features).filter(
    ([name]) => FEATURE_METADATA[name]?.category === "advanced"
  )
  const unknownFeatures = Object.entries(features).filter(
    ([name]) => !FEATURE_METADATA[name]
  )

  const openSettings = (name: string) => {
    const info = FEATURE_METADATA[name]
    if (!info) return

    // Extract tool name from feature name (e.g., "mcp_filesystem" -> "filesystem")
    const toolName = name.replace("mcp_", "")
    setSettingsDialog({
      open: true,
      toolName,
      toolLabel: info.label,
    })
  }

  const closeSettings = () => {
    setSettingsDialog(null)
  }

  const handleConfigSave = () => {
    // Config is already saved by the dialog, just close
    closeSettings()
  }

  return (
    <div className="space-y-6">
      {/* Core Features */}
      {coreFeatures.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Core Features</CardTitle>
            <CardDescription>
              Essential functionality for your knowledge base
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {coreFeatures.map(([name, enabled], index) => (
              <div key={name}>
                <FeatureToggle
                  name={name}
                  enabled={enabled}
                  onToggle={onToggle}
                />
                {index < coreFeatures.length - 1 && <Separator />}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* MCP Tools */}
      {mcpFeatures.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>MCP Tools</CardTitle>
            <CardDescription>
              Model Context Protocol integrations for extended capabilities
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {mcpFeatures.map(([name, enabled], index) => (
              <div key={name}>
                <FeatureToggle
                  name={name}
                  enabled={enabled}
                  onToggle={onToggle}
                  onOpenSettings={() => openSettings(name)}
                />
                {index < mcpFeatures.length - 1 && <Separator />}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Advanced Features */}
      {advancedFeatures.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Advanced Features</CardTitle>
            <CardDescription>
              Experimental and power-user features
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {advancedFeatures.map(([name, enabled], index) => (
              <div key={name}>
                <FeatureToggle name={name} enabled={enabled} onToggle={onToggle} />
                {index < advancedFeatures.length - 1 && <Separator />}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Unknown features (fallback) */}
      {unknownFeatures.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Other</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {unknownFeatures.map(([name, enabled], index) => (
              <div key={name}>
                <FeatureToggle
                  name={name}
                  enabled={enabled}
                  onToggle={onToggle}
                />
                {index < unknownFeatures.length - 1 && <Separator />}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* MCP Settings Dialog */}
      {settingsDialog && (
        <McpSettingsDialog
          toolName={settingsDialog.toolName}
          toolLabel={settingsDialog.toolLabel}
          config={(mcpConfig?.[settingsDialog.toolName] as Record<string, unknown>) || {}}
          open={settingsDialog.open}
          onOpenChange={(open) => !open && closeSettings()}
          onSave={handleConfigSave}
        />
      )}
    </div>
  )
}
