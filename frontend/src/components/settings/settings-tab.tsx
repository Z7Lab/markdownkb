import { useSettings } from "@/hooks/use-settings"
import { LlmConfig } from "./llm-config"
import { SourcesPanel } from "./sources-panel"
import { FeaturesPanel } from "./features-panel"
import { SystemPromptPanel } from "./system-prompt-panel"
import { EmbeddingPanel } from "./embedding-panel"

export function SettingsTab() {
  const {
    settings,
    providerStatus,
    modelStatus,
    indexStatus,
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
    reindex,
    cancelIndex,
    saveSystemPrompt,
    installEmbeddingModel,
    switchEmbeddingModel,
  } = useSettings()

  if (!settings) {
    return <div className="p-4 text-muted-foreground">Loading settings...</div>
  }

  return (
    <div className="p-4 space-y-6 overflow-y-auto h-full">
      <h2 className="text-lg font-semibold">Settings</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
        <SourcesPanel
          sources={settings.sources}
          onAdd={addSource}
          onRemove={removeSource}
        />
      </div>

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

      <FeaturesPanel
        features={settings.features}
        onToggle={toggleFeature}
      />

      <SystemPromptPanel
        prompt={settings.system_prompt}
        defaultPrompt={settings.default_system_prompt}
        onSave={saveSystemPrompt}
      />
    </div>
  )
}
