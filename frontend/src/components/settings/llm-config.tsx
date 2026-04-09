import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Download, Eye, EyeOff, HelpCircle, Loader2, X } from "lucide-react"
import type { AppSettings, ModelEntry, ModelInfo } from "@/lib/types"
import type { OllamaPullProgress } from "@/hooks/use-provider-settings"
import { TestPrompt } from "./test-prompt"
import { GenerationParams } from "./generation-params"
import { LlmSetupGuide } from "@/components/llm-setup-guide"

/** Provider types shown in the dropdown */
const KNOWN_PROVIDERS: { name: string; label: string; defaultBase: string; guideKey: string; needsKey: boolean }[] = [
  { name: "ollama", label: "Ollama (local)", defaultBase: "http://localhost:11434", guideKey: "ollama", needsKey: false },
  { name: "llamacpp", label: "llama.cpp (local)", defaultBase: "http://localhost:8080/v1", guideKey: "llamacpp", needsKey: false },
  { name: "anthropic", label: "Anthropic", defaultBase: "", guideKey: "cloud", needsKey: true },
  { name: "venice", label: "Venice", defaultBase: "https://api.venice.ai/api/v1", guideKey: "cloud", needsKey: true },
  { name: "custom", label: "Custom (OpenAI-compatible)", defaultBase: "http://localhost:8080/v1", guideKey: "custom", needsKey: false },
]

export function LlmConfig({
  settings,
  providerStatus,
  modelStatus,
  onSave,
  onSaveLlmParams,
  onTestProvider,
  onPingModel,
  onRefreshModels,
  onFetchModelInfo,
  pullProgress,
  onPullModel,
  onCancelPull,
  onFetchOllamaStatus,
  onClearStatus,
}: {
  settings: AppSettings
  providerStatus: string
  modelStatus: string
  onSave: (name: string, model: string, apiBase: string, apiKey: string) => Promise<void>
  onSaveLlmParams: (temperature: number, maxTokens: number, numCtx: number | null) => Promise<void>
  onTestProvider: (name: string, model: string, apiBase: string, apiKey: string) => Promise<void>
  onPingModel: (name: string, model: string, apiBase: string, apiKey: string, signal?: AbortSignal) => Promise<void>
  onRefreshModels: (name: string, apiBase: string) => Promise<{ models: ModelEntry[]; status: string }>
  onFetchModelInfo: (model: string, apiBase: string) => Promise<ModelInfo>
  pullProgress: OllamaPullProgress
  onPullModel: (modelName: string, apiBase?: string) => Promise<void>
  onCancelPull: () => void
  onFetchOllamaStatus: () => Promise<{ reachable: boolean; api_base: string; starter_models: { name: string; description: string }[] }>
  onClearStatus?: () => void
}) {
  const [provider, setProvider] = useState(settings.active_provider)
  const [model, setModel] = useState(settings.active_model)
  const [apiBase, setApiBase] = useState(settings.active_api_base)
  const [apiKey, setApiKey] = useState("")
  const activeProvider = settings.providers.find((p) => p.name === provider)
  const keyFromEnv = activeProvider?.api_key_source === "env"
  const keyIsSet = activeProvider?.api_key_set ?? false
  const [showKey, setShowKey] = useState(false)
  const [models, setModels] = useState<ModelEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [customMode, setCustomMode] = useState(false)

  const userPickedModel = useRef(false)

  // Re-sync local state when settings change externally (e.g. after save)
  const prevSettingsRef = useRef(settings)
  useEffect(() => {
    const prev = prevSettingsRef.current
    prevSettingsRef.current = settings
    if (
      prev.active_provider !== settings.active_provider
      || prev.active_model !== settings.active_model
      || prev.active_api_base !== settings.active_api_base
    ) {
      setProvider(settings.active_provider)
      setModel(settings.active_model)
      setApiBase(settings.active_api_base)
      setApiKey("")
      userPickedModel.current = false
    }
  }, [settings])

  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null)
  const [infoLoading, setInfoLoading] = useState(false)

  const [pingLoading, setPingLoading] = useState(false)
  const pingAbortRef = useRef<AbortController | null>(null)

  const isOllama = provider.toLowerCase().includes("ollama")
  const [pullModelName, setPullModelName] = useState("")
  const [ollamaStatus, setOllamaStatus] = useState<{ reachable: boolean; starter_models: { name: string; description: string }[] } | null>(null)

  const handleRefresh = useCallback(async () => {
    setLoading(true)
    try {
      const res = await onRefreshModels(provider, apiBase)
      if (res.models.length > 0) {
        const entries = res.models as ModelEntry[]
        setModels(entries)
        if (!userPickedModel.current && !entries.some((m) => m.id === model)) {
          setModel(entries[0].id)
        }
        setCustomMode(false)
      }
    } finally {
      setLoading(false)
    }
  }, [onRefreshModels, provider, apiBase, model])

  useEffect(() => {
    if (!isOllama) { setOllamaStatus(null); return }
    onFetchOllamaStatus()
      .then((s) => setOllamaStatus({ reachable: s.reachable, starter_models: s.starter_models }))
      .catch(() => setOllamaStatus(null))
  }, [isOllama, onFetchOllamaStatus])

  // After a successful pull, refresh the model list
  useEffect(() => {
    if (pullProgress.done) {
      handleRefresh()
    }
  }, [pullProgress.done, handleRefresh])

  useEffect(() => {
    let cancelled = false
    async function fetchModels() {
      setLoading(true)
      try {
        const res = await onRefreshModels(provider, apiBase)
        if (!cancelled && res.models.length > 0) {
          setModels(res.models as ModelEntry[])
          setCustomMode(false)
        }
      } catch (err) {
        console.warn("Failed to fetch model list:", (err as Error).message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    userPickedModel.current = false
    fetchModels()
    return () => { cancelled = true }
  }, [provider, apiBase, onRefreshModels])

  useEffect(() => {
    if (!model) { setModelInfo(null); return }
    const timer = setTimeout(async () => {
      setInfoLoading(true)
      try {
        const info = await onFetchModelInfo(model, apiBase)
        setModelInfo(info)
      } catch (err) {
        console.warn("Failed to fetch model info:", (err as Error).message)
        setModelInfo(null)
      } finally {
        setInfoLoading(false)
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [model, apiBase, onFetchModelInfo])

  // Determine status for each provider type
  const configuredMap = new Map(settings.providers.map((p) => [p.name, p]))
  const allProviders = KNOWN_PROVIDERS.map((kp) => {
    const saved = configuredMap.get(kp.name)
    let status: "ready" | "needs-key" | "saved" | ""
    if (saved) {
      if (kp.needsKey && !saved.api_key_set) {
        status = "needs-key"
      } else {
        status = "ready"
      }
    } else {
      status = ""
    }
    return { ...kp, status, saved }
  })

  const selectedProviderInfo = allProviders.find((p) => p.name === provider)
  const hasSavedConfig = !!selectedProviderInfo?.saved
  const showGuide = !hasSavedConfig || selectedProviderInfo?.status === "needs-key"

  function onProviderChange(name: string) {
    setProvider(name)
    setModels([])
    setCustomMode(false)
    userPickedModel.current = false
    onClearStatus?.()
    const saved = configuredMap.get(name)
    if (saved) {
      setModel(saved.model)
      setApiBase(saved.api_base)
      setApiKey("")
    } else {
      const known = KNOWN_PROVIDERS.find((kp) => kp.name === name)
      setModel("")
      setApiBase(known?.defaultBase ?? "")
      setApiKey("")
    }
  }

  function onModelChange(value: string) {
    userPickedModel.current = true
    setModel(value)
  }

  async function handlePing() {
    pingAbortRef.current?.abort()
    const controller = new AbortController()
    pingAbortRef.current = controller
    setPingLoading(true)
    try {
      await onPingModel(provider, model, apiBase, apiKey, controller.signal)
    } finally {
      setPingLoading(false)
    }
  }

  function handleCancelPing() {
    pingAbortRef.current?.abort()
    pingAbortRef.current = null
    setPingLoading(false)
  }

  const selectOptions = [...models]
  if (model && !models.some((m) => m.id === model)) {
    selectOptions.unshift({ id: model, label: model })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>LLM Configuration</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label htmlFor="llm-provider" className="text-sm font-medium">Provider</label>
          <div className="flex gap-2">
            <Select value={provider} onValueChange={onProviderChange}>
              <SelectTrigger id="llm-provider" className="flex-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {allProviders.map((p) => (
                  <SelectItem key={p.name} value={p.name}>
                    <span className="flex items-center gap-2">
                      {p.label}
                      {p.status === "ready" && (
                        <Badge variant="secondary" className="text-[10px] px-1.5 py-0 text-green-600">ready</Badge>
                      )}
                      {p.status === "needs-key" && (
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-amber-600">needs key</Badge>
                      )}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" onClick={() => onTestProvider(provider, model, apiBase, apiKey)}>
              Test
            </Button>
          </div>
          {provider === "custom" && (
            <p className="text-xs text-muted-foreground mt-1">
              Works with LM Studio, vLLM, text-generation-webui, or any server that exposes an OpenAI-compatible <code className="text-[10px]">/v1/chat/completions</code> endpoint.
            </p>
          )}
          {providerStatus && (
            <pre className="text-sm bg-muted p-3 rounded-md whitespace-pre-wrap mt-2">
              {providerStatus}
            </pre>
          )}
        </div>

        {/* Show setup guide for unconfigured or key-missing providers */}
        {showGuide && selectedProviderInfo && (
          <LlmSetupGuide
            onNavigateSettings={() => {}}
            initialProvider={selectedProviderInfo.guideKey as "ollama" | "llamacpp" | "cloud" | "custom"}
            embedded
          />
        )}

        <div>
          <label htmlFor="llm-api-base" className="text-sm font-medium">API Base</label>
          <Input
            id="llm-api-base"
            value={apiBase}
            onChange={(e) => setApiBase(e.target.value)}
            placeholder="Leave empty for default"
          />
          {!isOllama && !provider.toLowerCase().includes("anthropic") && (
            <p className="text-xs text-muted-foreground mt-1">
              Works with any OpenAI-compatible server — llama.cpp (<code className="text-[10px]">:8080/v1</code>),
              LM Studio (<code className="text-[10px]">:1234/v1</code>),
              vLLM (<code className="text-[10px]">:8000/v1</code>).
              Use <code className="text-[10px]">openai/model-name</code> as the model ID.
            </p>
          )}
        </div>

        <div>
          <label htmlFor="llm-api-key" className="text-sm font-medium">API Key</label>
          {keyFromEnv ? (
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="secondary">{provider.toUpperCase()}_API_KEY</Badge>
              <span className="text-xs text-muted-foreground">Set via environment variable</span>
            </div>
          ) : (
            <div className="flex gap-2">
              <Input
                id="llm-api-key"
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={keyIsSet ? "Key set (leave empty to keep)" : "Enter API key or set via env var"}
                className="flex-1"
              />
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowKey(!showKey)}
                aria-label={showKey ? "Hide API key" : "Show API key"}
              >
                {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
          )}
          <p className="text-xs text-muted-foreground mt-1">
            {keyFromEnv
              ? "Managed via secrets/ file or environment variable. Update and restart to change."
              : `Set ${provider.toUpperCase()}_API_KEY via secrets/${provider.toLowerCase()}_api_key file or environment variable.`}
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="llm-model" className="text-sm font-medium">Model</label>
          <div className="flex gap-2">
            {customMode ? (
              <Input
                id="llm-model"
                value={model}
                onChange={(e) => { userPickedModel.current = true; setModel(e.target.value) }}
                className="flex-1"
                placeholder="e.g. openai/gpt-4o or openai/deepseek-r1-671b"
                autoFocus
              />
            ) : (
              <Select value={model} onValueChange={onModelChange}>
                <SelectTrigger id="llm-model" className="flex-1" disabled={loading}>
                  <SelectValue placeholder={loading ? "Loading models..." : "Select model"} />
                </SelectTrigger>
                <SelectContent>
                  {selectOptions.map((m) => (
                    <SelectItem key={m.id} value={m.id}>{m.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
              Refresh
            </Button>
          </div>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground cursor-help"
                  onClick={() => setCustomMode(!customMode)}
                >
                  <HelpCircle className="h-3 w-3" />
                  {customMode ? "Choose from list" : "Type manually"}
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-72">
                {customMode
                  ? "Switch back to picking a model from the dropdown list."
                  : "Type a model ID directly, e.g. openai/gpt-4o. For any OpenAI-compatible server (llama.cpp, vLLM, LM Studio, etc.) use openai/<model-name> with a custom API Base URL."}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {infoLoading && (
            <p className="text-xs text-muted-foreground">Loading model info...</p>
          )}
          {modelInfo && !modelInfo.error && !infoLoading && (
            <div className="text-xs text-muted-foreground bg-muted/50 rounded-md p-3 space-y-1">
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                {modelInfo.max_input_tokens != null && (
                  <span>Context: {(modelInfo.max_input_tokens / 1000).toFixed(0)}k</span>
                )}
                {modelInfo.max_output_tokens != null && (
                  <span>Max output: {(modelInfo.max_output_tokens / 1000).toFixed(0)}k</span>
                )}
                {modelInfo.input_cost_per_token != null && modelInfo.input_cost_per_token > 0 && (
                  <span>In: ${(modelInfo.input_cost_per_token * 1_000_000).toFixed(2)}/M</span>
                )}
                {modelInfo.output_cost_per_token != null && modelInfo.output_cost_per_token > 0 && (
                  <span>Out: ${(modelInfo.output_cost_per_token * 1_000_000).toFixed(2)}/M</span>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {modelInfo.supports_vision && <Badge variant="secondary">Vision</Badge>}
                {modelInfo.supports_function_calling && <Badge variant="secondary">Tools</Badge>}
                {modelInfo.supports_response_schema && <Badge variant="secondary">Structured</Badge>}
                {modelInfo.supports_pdf_input && <Badge variant="secondary">PDF</Badge>}
                {modelInfo.ollama_details && (
                  <>
                    {modelInfo.ollama_details.parameter_size && (
                      <Badge variant="outline">{modelInfo.ollama_details.parameter_size}</Badge>
                    )}
                    {modelInfo.ollama_details.quantization_level && (
                      <Badge variant="outline">{modelInfo.ollama_details.quantization_level}</Badge>
                    )}
                    {modelInfo.ollama_details.family && (
                      <Badge variant="outline">{modelInfo.ollama_details.family}</Badge>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {isOllama && ollamaStatus?.reachable && (
          <div className="border rounded-md p-3 space-y-3">
            <div className="text-sm font-medium">Pull a Model from Ollama</div>
            <div className="flex gap-2">
              <Input
                value={pullModelName}
                onChange={(e) => setPullModelName(e.target.value)}
                placeholder="e.g. qwen3:8b"
                className="flex-1"
                disabled={pullProgress.pulling}
              />
              <Button
                size="sm"
                variant="outline"
                onClick={() => pullModelName.trim() && onPullModel(pullModelName.trim())}
                disabled={pullProgress.pulling || !pullModelName.trim()}
              >
                {pullProgress.pulling ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                <span className="ml-1">{pullProgress.pulling ? "Pulling..." : "Pull"}</span>
              </Button>
              {pullProgress.pulling && (
                <Button size="sm" variant="ghost" onClick={onCancelPull}>
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
            {ollamaStatus.starter_models.length > 0 && !pullProgress.pulling && (
              <div className="flex flex-wrap gap-1.5">
                <span className="text-xs text-muted-foreground mr-1">Suggested:</span>
                {ollamaStatus.starter_models.map((m) => (
                  <button
                    key={m.name}
                    type="button"
                    className="text-xs px-2 py-0.5 rounded-full border hover:bg-accent transition-colors"
                    onClick={() => setPullModelName(m.name)}
                    title={m.description}
                  >
                    {m.name}
                  </button>
                ))}
              </div>
            )}
            {pullProgress.pulling && (
              <div className="space-y-1">
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all duration-300"
                    style={{ width: `${Math.max(pullProgress.percent, 1)}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground">{pullProgress.status} — {pullProgress.percent.toFixed(0)}%</p>
              </div>
            )}
            {pullProgress.done && !pullProgress.pulling && (
              <p className="text-xs text-green-600">Model pulled successfully. Select it from the dropdown above.</p>
            )}
            {pullProgress.error && (
              <p className="text-xs text-destructive">{pullProgress.error}</p>
            )}
          </div>
        )}

        {isOllama && ollamaStatus && !ollamaStatus.reachable && (
          <div className="border border-amber-200 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-800 rounded-md p-3">
            <p className="text-sm text-amber-800 dark:text-amber-200">
              Cannot reach Ollama at <code className="text-xs">{apiBase || "unknown"}</code>.
              Make sure Ollama is installed and running.
            </p>
          </div>
        )}

        <div className="flex gap-2">
          <Button onClick={() => onSave(provider, model, apiBase, apiKey)}>
            Save
          </Button>
          <Button variant="outline" onClick={handlePing} disabled={pingLoading}>
            {pingLoading ? "Pinging..." : "Ping Model"}
          </Button>
          {pingLoading && (
            <Button variant="secondary" size="sm" onClick={handleCancelPing}>
              Cancel
            </Button>
          )}
        </div>

        {modelStatus && (
          <pre className="text-sm bg-muted p-3 rounded-md whitespace-pre-wrap">
            {modelStatus}
          </pre>
        )}

        <TestPrompt provider={provider} model={model} apiBase={apiBase} apiKey={apiKey} />

        <GenerationParams
          initialTemperature={activeProvider?.temperature ?? settings.temperature}
          initialMaxTokens={activeProvider?.max_tokens ?? settings.max_tokens}
          initialNumCtx={activeProvider?.num_ctx ?? settings.num_ctx ?? null}
          isOllama={isOllama}
          isCloud={provider === "anthropic" || provider === "venice" || provider === "openai"}
          modelInfo={modelInfo}
          onSave={onSaveLlmParams}
        />
      </CardContent>
    </Card>
  )
}
