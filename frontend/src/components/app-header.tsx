import type { LucideIcon } from "lucide-react"
import { TabsList, TabsTrigger } from "@/components/ui/tabs"
import { IndexActivityIndicator } from "@/components/index-activity-indicator"
import { LLMStatusIndicator } from "@/components/llm-status-indicator"
import { useSettings } from "@/hooks/use-settings"

interface PluginTabTriggerProps {
  pluginKey: string
  value: string
  icon: LucideIcon
  label: string
}

function PluginTabTrigger({ pluginKey, value, icon: Icon, label }: PluginTabTriggerProps) {
  const { settings } = useSettings()
  const plugins = settings?.plugins_enabled as Record<string, boolean> | undefined
  if (!plugins?.[pluginKey]) return null
  return (
    <TabsTrigger value={value}>
      <Icon className="h-4 w-4" />
      {label}
    </TabsTrigger>
  )
}

interface TabDef {
  value: string
  icon: LucideIcon
  label: string
  pluginKey?: string
}

export function AppHeader({ tabs, onLogoClick }: {
  tabs: TabDef[]
  onLogoClick: () => void
}) {
  return (
    <header className="shrink-0 z-20 bg-background border-b px-6 py-3 flex items-center justify-between">
      <button
        className="text-left hover:opacity-70 transition-opacity"
        onClick={onLogoClick}
      >
        <h1 className="text-lg font-bold tracking-tight">MarkdownKB</h1>
        <p className="text-xs text-muted-foreground">
          Knowledge base assistant
        </p>
      </button>
      <div className="flex items-center gap-4">
        <IndexActivityIndicator />
        <LLMStatusIndicator />
        <TabsList>
          {tabs.map((tab) =>
            tab.pluginKey ? (
              <PluginTabTrigger
                key={tab.value}
                pluginKey={tab.pluginKey}
                value={tab.value}
                icon={tab.icon}
                label={tab.label}
              />
            ) : (
              <TabsTrigger key={tab.value} value={tab.value}>
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </TabsTrigger>
            ),
          )}
        </TabsList>
      </div>
    </header>
  )
}
