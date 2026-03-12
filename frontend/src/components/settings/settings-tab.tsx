import { useEffect, useState } from "react"
import { useSettings } from "@/hooks/use-settings"
import { useIndexEvents } from "@/hooks/use-index-events"
import { api } from "@/lib/api"
import { AppSidebar } from "@/components/ui/app-sidebar"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import {
  Cpu,
  Database,
  FolderCog,
  Layers,
  MessageSquareText,
  ScrollText,
  Search,
  ToggleRight,
} from "lucide-react"
import { LlmConfig } from "./llm-config"
import { SourcesPanel } from "./sources-panel"
import { PluginsPanel } from "./plugins-panel"
import { SystemPromptPanel } from "./system-prompt-panel"
import { EmbeddingPanel } from "./embedding-panel"
import { SearchPanel } from "./search-panel"
import { DatabasePanel } from "./database-panel"
import { LoggingPanel } from "./logging-panel"
import { ScopesPanel } from "./scopes-panel"
import { Library } from "lucide-react"

const sections = [
  { id: "llm", label: "LLM Provider", icon: Cpu },
  { id: "search", label: "Search", icon: Search },
  { id: "sources", label: "Sources", icon: FolderCog },
  { id: "scopes", label: "Scopes", icon: Library },
  { id: "embeddings", label: "Embeddings", icon: Layers },
  { id: "features", label: "Plugins", icon: ToggleRight },
  { id: "prompt", label: "System Prompt", icon: MessageSquareText },
  { id: "database", label: "Database", icon: Database },
  { id: "logging", label: "Logging", icon: ScrollText },
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
    saveLlmParams,
    testConnection,
    refreshModels,
    pingModel,
    fetchModelInfo,
    toggleFeature,
    addSource,
    removeSource,
    addIgnorePattern,
    removeIgnorePattern,
    addProjectRoot,
    removeProjectRoot,
    updateProjectRoot,
    reindex,
    cancelIndex,
    saveSystemPrompt,
    saveSearchSummaryPrompt,
    saveRetrievalSettings,
    installEmbeddingModel,
    uninstallEmbeddingModel,
    switchEmbeddingModel,
    toggleIntelligentSearch,
    setLogLevel,
  } = useSettings()

  const { errorCount, clearErrors } = useIndexEvents()
  const [availableTags, setAvailableTags] = useState<string[]>([])

  useEffect(() => {
    if (activeSection === "scopes") {
      api.get<{ items: string[] }>("/api/tags").then((r) => setAvailableTags(r.items)).catch(() => { /* tags list is supplementary */ })
    }
  }, [activeSection])

  if (!settings) {
    return <div className="p-4 text-muted-foreground">Loading settings...</div>
  }

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <AppSidebar
        header={<h3 className="text-sm font-semibold text-muted-foreground">Settings</h3>}
      >
        <nav aria-label="Settings sections" className="p-2 space-y-0.5">
          {sections.map((s) => (
            <button
              key={s.id}
              type="button"
              className={cn(
                "w-full text-left rounded-md px-3 py-2 text-sm flex items-center gap-2 hover:bg-accent",
                activeSection === s.id && "bg-accent font-medium",
              )}
              aria-current={activeSection === s.id ? "page" : undefined}
              onClick={() => {
                setActiveSection(s.id)
                if (s.id === "sources" && errorCount > 0) clearErrors()
              }}
            >
              <s.icon className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate flex-1">{s.label}</span>
              {s.id === "sources" && errorCount > 0 && (
                <span className="inline-flex items-center justify-center h-5 min-w-5 px-1 rounded-full bg-error text-error-foreground text-xs font-medium tabular-nums">
                  {errorCount}
                </span>
              )}
            </button>
          ))}
        </nav>
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
                onSaveLlmParams={saveLlmParams}
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
                topK={settings.top_k}
                defaultTopK={settings.default_top_k}
                scoreThreshold={settings.score_threshold}
                defaultScoreThreshold={settings.default_score_threshold}
                hybridSearch={settings.hybrid_search}
                defaultHybridSearch={settings.default_hybrid_search}
                bm25Weight={settings.bm25_weight}
                defaultBm25Weight={settings.default_bm25_weight}
                onToggle={toggleIntelligentSearch}
                onSavePrompt={saveSearchSummaryPrompt}
                onSaveRetrievalSettings={saveRetrievalSettings}
              />
            )}
            {activeSection === "sources" && (
              <SourcesPanel
                sources={settings.sources}
                ignorePatterns={settings.global_ignore}
                projectRoots={settings.project_roots}
                onAdd={addSource}
                onRemove={removeSource}
                onAddIgnore={addIgnorePattern}
                onRemoveIgnore={removeIgnorePattern}
                onAddProjectRoot={addProjectRoot}
                onRemoveProjectRoot={removeProjectRoot}
                onUpdateProjectRoot={updateProjectRoot}
              />
            )}
            {activeSection === "scopes" && (
              <ScopesPanel folders={settings.sources} availableTags={availableTags} />
            )}
            {activeSection === "embeddings" && (
              <EmbeddingPanel
                models={embeddingModels}
                activeModel={settings.embedding_model}
                status={embeddingStatus}
                switching={embeddingSwitching}
                onInstall={installEmbeddingModel}
                onUninstall={uninstallEmbeddingModel}
                onSwitch={switchEmbeddingModel}
                onReindex={reindex}
                onCancel={cancelIndex}
              />
            )}
            {activeSection === "features" && (
              <PluginsPanel
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
            {activeSection === "database" && (
              <DatabasePanel />
            )}
            {activeSection === "logging" && (
              <LoggingPanel
                logLevel={settings.log_level}
                onSetLogLevel={setLogLevel}
              />
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
