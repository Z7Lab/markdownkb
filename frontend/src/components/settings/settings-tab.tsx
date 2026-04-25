import { useEffect, useState } from "react"
import { useLocation } from "wouter"
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
  Plug,
  RefreshCw,
  ScrollText,
  Search,
  Shield,
  ToggleRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { LlmConfig } from "./llm-config"
import { SourcesPanel } from "./sources-panel"
import { PluginsPanel } from "./plugins-panel"
import { SystemPromptPanel } from "./system-prompt-panel"
import { EmbeddingPanel } from "./embedding-panel"
import { SearchPanel } from "./retrieval-panel"
import { DatabasePanel } from "./database-panel"
import { BackupPanel } from "./backup-panel"
import { AboutPanel } from "./about-panel"
import { LoggingPanel } from "./logging-panel"
import { ScopesPanel } from "./scopes-panel"
import { BucketsPanel } from "./buckets-panel"
import { McpPanel } from "./mcp-panel"
import { SecurityPanel } from "./security-panel"
import { Library, Archive, HardDriveDownload, Info } from "lucide-react"

const sections = [
  { id: "llm", label: "Chat Model", icon: Cpu },
  { id: "embeddings", label: "Embedding Model", icon: Layers },
  { id: "search", label: "Retrieval", icon: Search },
  { id: "sources", label: "Sources", icon: FolderCog },
  { id: "scopes", label: "Scopes", icon: Library },
  { id: "buckets", label: "Buckets", icon: Archive, plugin: "buckets" },
  { id: "features", label: "Plugins", icon: ToggleRight },
  { id: "mcp", label: "MCP", icon: Plug },
  { id: "prompt", label: "System Prompt", icon: MessageSquareText },
  { id: "security", label: "Security", icon: Shield },
  { id: "database", label: "Database", icon: Database },
  { id: "backup", label: "Backup & Restore", icon: HardDriveDownload },
  { id: "logging", label: "Logging", icon: ScrollText },
  { id: "about", label: "About", icon: Info },
] as const

type SectionId = (typeof sections)[number]["id"]

export function SettingsTab({ initialSection }: { initialSection?: string } = {}) {
  const [, setLocation] = useLocation()
  const [activeSection, setActiveSection] = useState<SectionId>(
    () => (initialSection && sections.some((s) => s.id === initialSection)
      ? (initialSection as SectionId)
      : "llm"),
  )

  // If the route changes (e.g. navigating from /settings/sources to /settings/mcp),
  // update the active section to match.
  useEffect(() => {
    if (initialSection && sections.some((s) => s.id === initialSection)) {
      setActiveSection(initialSection as SectionId)
    }
  }, [initialSection])
  const {
    settings,
    providerStatus,
    modelStatus,
    clearStatus,
    embeddingModels,
    embeddingStatus,
    embeddingSwitching,
    saveProvider,
    saveLlmParams,
    testConnection,
    refreshModels,
    pingModel,
    fetchModelInfo,
    toggleCore,
    toggleMcpFlag,
    togglePlugin,
    addSource,
    removeSource,
    addIgnorePattern,
    reload,
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
    pullProgress,
    pullOllamaModel,
    cancelPull,
    fetchOllamaStatus,
  } = useSettings()

  const { errorCount, clearErrors } = useIndexEvents()
  const [availableTags, setAvailableTags] = useState<string[]>([])
  const [dirty, setDirty] = useState(false)
  const [applying, setApplying] = useState(false)

  useEffect(() => {
    api.post("/api/v1/settings/reload", {}).catch(() => { /* non-critical */ })
  }, [])

  useEffect(() => {
    const check = () => {
      api.get<{ dirty: boolean }>("/api/v1/settings/status")
        .then((r) => setDirty(r.dirty))
        .catch(() => { /* non-critical */ })
    }
    check()
    const id = setInterval(check, 10_000)
    return () => clearInterval(id)
  }, [])

  async function handleApply() {
    setApplying(true)
    try {
      await api.post("/api/v1/settings/reload", {})
      setDirty(false)
      toast.success("Settings applied")
    } catch {
      toast.error("Failed to apply settings")
    } finally {
      setApplying(false)
    }
  }

  useEffect(() => {
    if (activeSection === "scopes") {
      api.get<{ items: string[] }>("/api/v1/tags").then((r) => setAvailableTags(r.items)).catch(() => { /* tags list is supplementary */ })
    }
  }, [activeSection])

  const visibleSections = sections.filter(
    (s) => !("plugin" in s) || settings?.plugins_enabled?.[s.plugin],
  )

  if (!settings) {
    return <div className="p-4 text-muted-foreground">Loading settings...</div>
  }

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <AppSidebar
        header={<h3 className="text-sm font-semibold text-muted-foreground">Settings</h3>}
      >
        <nav aria-label="Settings sections" className="p-2 space-y-0.5">
          {visibleSections.map((s) => (
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
                setLocation(`/settings/${s.id}`, { replace: true })
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
          {dirty && (
            <div className="pt-2 px-1">
              <Button
                size="sm"
                className="w-full gap-1.5"
                onClick={handleApply}
                disabled={applying}
              >
                <RefreshCw className={cn("h-3.5 w-3.5", applying && "animate-spin")} />
                Apply Updates
              </Button>
            </div>
          )}
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
                pullProgress={pullProgress}
                onPullModel={pullOllamaModel}
                onCancelPull={cancelPull}
                onFetchOllamaStatus={fetchOllamaStatus}
                onClearStatus={clearStatus}
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
                sourceConfigs={settings.source_configs}
                ignorePatterns={settings.global_ignore}
                projectRoots={settings.project_roots}
                coreVersioningEnabled={settings.core.versioning ?? true}
                onReloadSettings={reload}
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
            {activeSection === "buckets" && (
              <BucketsPanel />
            )}
            {activeSection === "embeddings" && (
              <EmbeddingPanel
                models={embeddingModels}
                activeModel={settings.embedding_model}
                provider={settings.embedding_provider ?? "local"}
                remoteConfig={settings.embedding_remote_config ?? null}
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
                mcpConfig={settings.mcp}
                onToggleCore={toggleCore}
                onToggleMcpFlag={toggleMcpFlag}
                onTogglePlugin={togglePlugin}
              />
            )}
            {activeSection === "mcp" && (
              <McpPanel onToggleMcpFlag={toggleMcpFlag} />
            )}
            {activeSection === "prompt" && (
              <SystemPromptPanel
                prompt={settings.system_prompt}
                defaultPrompt={settings.default_system_prompt}
                onSave={saveSystemPrompt}
              />
            )}
            {activeSection === "security" && (
              <SecurityPanel />
            )}
            {activeSection === "database" && (
              <DatabasePanel />
            )}
            {activeSection === "backup" && (
              <BackupPanel />
            )}
            {activeSection === "logging" && (
              <LoggingPanel
                logLevel={settings.log_level}
                onSetLogLevel={setLogLevel}
              />
            )}
            {activeSection === "about" && (
              <AboutPanel onEnableUpdateCheck={async () => { await toggleCore("update_check", true) }} />
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
