import { useSettings } from "@/hooks/use-settings"
import { LlmConfig } from "./llm-config"
import { SourcesPanel } from "./sources-panel"
import { IndexPanel } from "./index-panel"
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <EmbeddingPanel
          models={embeddingModels}
          activeModel={settings.embedding_model}
          status={embeddingStatus}
          switching={embeddingSwitching}
          onInstall={installEmbeddingModel}
          onSwitch={switchEmbeddingModel}
        />
        <IndexPanel
          status={indexStatus}
          onReindex={reindex}
          onCancel={cancelIndex}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <FeaturesPanel
          features={settings.features}
          onToggle={toggleFeature}
        />
      </div>

      <SystemPromptPanel
        prompt={settings.system_prompt}
        defaultPrompt={settings.default_system_prompt}
        onSave={saveSystemPrompt}
      />
    </div>
  )
}
