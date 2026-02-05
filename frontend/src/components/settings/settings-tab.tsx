import { useSettings } from "@/hooks/use-settings"
import { LlmConfig } from "./llm-config"
import { SourcesPanel } from "./sources-panel"
import { IndexPanel } from "./index-panel"
import { FeaturesPanel } from "./features-panel"

export function SettingsTab() {
  const {
    settings,
    status,
    indexStatus,
    saveProvider,
    testConnection,
    refreshModels,
    toggleFeature,
    addSource,
    removeSource,
    reindex,
    cancelIndex,
  } = useSettings()

  if (!settings) {
    return <div className="p-4 text-muted-foreground">Loading settings...</div>
  }

  return (
    <div className="p-4 space-y-6 overflow-y-auto h-[calc(100vh-4.5rem)]">
      <h2 className="text-lg font-semibold">Settings</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <LlmConfig
          settings={settings}
          status={status}
          onSave={saveProvider}
          onTest={testConnection}
          onRefreshModels={refreshModels}
        />
        <SourcesPanel
          sources={settings.sources}
          onAdd={addSource}
          onRemove={removeSource}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <IndexPanel
          status={indexStatus}
          onReindex={reindex}
          onCancel={cancelIndex}
        />
        <FeaturesPanel
          features={settings.features}
          onToggle={toggleFeature}
        />
      </div>
    </div>
  )
}
