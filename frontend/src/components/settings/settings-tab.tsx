import { useState } from "react"
import { useSettings } from "@/hooks/use-settings"
import { AppSidebar } from "@/components/ui/app-sidebar"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import {
  Cpu,
  FolderCog,
  Layers,
  MessageSquareText,
  Search,
  ToggleRight,
} from "lucide-react"
import { LlmConfig } from "./llm-config"
import { SourcesPanel } from "./sources-panel"
import { FeaturesPanel } from "./features-panel"
import { SystemPromptPanel } from "./system-prompt-panel"
import { EmbeddingPanel } from "./embedding-panel"
import { SearchPanel } from "./search-panel"

const sections = [
  { id: "llm", label: "LLM Provider", icon: Cpu },
  { id: "search", label: "Search", icon: Search },
  { id: "sources", label: "Sources", icon: FolderCog },
  { id: "embeddings", label: "Embeddings", icon: Layers },
  { id: "features", label: "Features", icon: ToggleRight },
  { id: "prompt", label: "System Prompt", icon: MessageSquareText },
] as const

type SectionId = (typeof sections)[number]["id"]

export function SettingsTab() {
  const [activeSection, setActiveSection] = useState<SectionId>("llm")
  const {
    settings,
    providerStatus,
    modelStatus,
    embeddingModels,
    embeddingStatus,
    embeddingSwitching,
    saveProvider,
    testConnection,
    refreshModels,
    pingModel,
    fetchModelInfo,
    toggleFeature,
    addSource,
    removeSource,
    addIgnorePattern,
    removeIgnorePattern,
    reindex,
    cancelIndex,
    saveSystemPrompt,
    saveSearchSummaryPrompt,
    installEmbeddingModel,
    switchEmbeddingModel,
    toggleIntelligentSearch,
  } = useSettings()

  if (!settings) {
    return <div className="p-4 text-muted-foreground">Loading settings...</div>
  }

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <AppSidebar
        header={<h3 className="text-sm font-semibold text-muted-foreground">Settings</h3>}
      >
        <div className="p-2 space-y-0.5">
          {sections.map((s) => (
            <button
              key={s.id}
              type="button"
              className={cn(
                "w-full text-left rounded-md px-3 py-2 text-sm flex items-center gap-2 hover:bg-accent",
                activeSection === s.id && "bg-accent font-medium",
              )}
              onClick={() => setActiveSection(s.id)}
            >
              <s.icon className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate">{s.label}</span>
            </button>
          ))}
        </div>
      </AppSidebar>
      <div className="flex-1 min-w-0 min-h-0">
        <ScrollArea className="h-full">
          <div className="p-6 max-w-3xl">
            {activeSection === "llm" && (
              <LlmConfig
                settings={settings}
                providerStatus={providerStatus}
                modelStatus={modelStatus}
                onSave={saveProvider}
                onTestProvider={testConnection}
                onPingModel={pingModel}
                onRefreshModels={refreshModels}
                onFetchModelInfo={fetchModelInfo}
              />
            )}
            {activeSection === "search" && (
              <SearchPanel
                intelligentSearchEnabled={settings.intelligent_search_enabled}
                searchSummaryPrompt={settings.search_summary_prompt}
                defaultSearchSummaryPrompt={settings.default_search_summary_prompt}
                onToggle={toggleIntelligentSearch}
                onSavePrompt={saveSearchSummaryPrompt}
              />
            )}
            {activeSection === "sources" && (
              <SourcesPanel
                sources={settings.sources}
                ignorePatterns={settings.global_ignore}
                onAdd={addSource}
                onRemove={removeSource}
                onAddIgnore={addIgnorePattern}
                onRemoveIgnore={removeIgnorePattern}
              />
            )}
            {activeSection === "embeddings" && (
              <EmbeddingPanel
                models={embeddingModels}
                activeModel={settings.embedding_model}
                status={embeddingStatus}
                switching={embeddingSwitching}
                onInstall={installEmbeddingModel}
                onSwitch={switchEmbeddingModel}
                onReindex={reindex}
                onCancel={cancelIndex}
              />
            )}
            {activeSection === "features" && (
              <FeaturesPanel
                features={settings.features}
                mcpConfig={settings.mcp}
                onToggle={toggleFeature}
              />
            )}
            {activeSection === "prompt" && (
              <SystemPromptPanel
                prompt={settings.system_prompt}
                defaultPrompt={settings.default_system_prompt}
                onSave={saveSystemPrompt}
              />
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
