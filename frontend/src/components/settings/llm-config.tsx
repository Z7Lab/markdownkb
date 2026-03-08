import { useEffect, useRef, useState } from "react"
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
import { Eye, EyeOff, HelpCircle } from "lucide-react"
import { Slider } from "@/components/ui/slider"
import type { AppSettings, ModelEntry, ModelInfo } from "@/lib/types"
import { TestPrompt } from "./test-prompt"

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
}: {
  settings: AppSettings
  providerStatus: string
  modelStatus: string
  onSave: (name: string, model: string, apiBase: string, apiKey: string) => Promise<void>
  onSaveLlmParams: (temperature: number, maxTokens: number, numCtx: number | null) => Promise<void>
  onTestProvider: (name: string, model: string, apiBase: string, apiKey: string) => Promise<void>
  onPingModel: (model: string, apiBase: string, apiKey: string, signal?: AbortSignal) => Promise<void>
  onRefreshModels: (name: string, apiBase: string) => Promise<{ models: ModelEntry[]; status: string }>
  onFetchModelInfo: (model: string, apiBase: string) => Promise<ModelInfo>
}) {
  const [provider, setProvider] = useState(settings.active_provider)
  const [model, setModel] = useState(settings.active_model)
  const [apiBase, setApiBase] = useState(settings.active_api_base)
  const [apiKey, setApiKey] = useState(() => {
    const active = settings.providers.find((p) => p.name === settings.active_provider)
    return active?.api_key ?? ""
  })
  const [showKey, setShowKey] = useState(false)
  const [models, setModels] = useState<ModelEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [customMode, setCustomMode] = useState(false)

  const userPickedModel = useRef(false)

  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null)
  const [infoLoading, setInfoLoading] = useState(false)

  const [pingLoading, setPingLoading] = useState(false)
  const pingAbortRef = useRef<AbortController | null>(null)

  const [temperature, setTemperature] = useState(settings.temperature)
  const [maxTokens, setMaxTokens] = useState(settings.max_tokens)
  const [numCtx, setNumCtx] = useState<string>(settings.num_ctx?.toString() ?? "")
  const [paramsDirty, setParamsDirty] = useState(false)
  const isOllama = provider.toLowerCase().includes("ollama")

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
      } catch {
        // silently fail — user can still type custom model
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
      } catch {
        setModelInfo(null)
      } finally {
        setInfoLoading(false)
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [model, apiBase, onFetchModelInfo])

  function onProviderChange(name: string) {
    setProvider(name)
    setModels([])
    setCustomMode(false)
    userPickedModel.current = false
    const p = settings.providers.find((x) => x.name === name)
    if (p) {
      setModel(p.model)
      setApiBase(p.api_base)
      setApiKey(p.api_key)
      setTemperature(p.temperature ?? settings.temperature)
      setMaxTokens(p.max_tokens ?? settings.max_tokens)
      setNumCtx(p.num_ctx?.toString() ?? "")
      setParamsDirty(false)
    }
  }

  function onModelChange(value: string) {
    userPickedModel.current = true
    setModel(value)
  }

  async function handleRefresh() {
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
  }

  async function handlePing() {
    pingAbortRef.current?.abort()
    const controller = new AbortController()
    pingAbortRef.current = controller
    setPingLoading(true)
    try {
      await onPingModel(model, apiBase, apiKey, controller.signal)
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
                {settings.providers.map((p) => (
                  <SelectItem key={p.name} value={p.name}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" onClick={() => onTestProvider(provider, model, apiBase, apiKey)}>
              Test Provider
            </Button>
          </div>
          {providerStatus && (
            <pre className="text-sm bg-muted p-3 rounded-md whitespace-pre-wrap mt-2">
              {providerStatus}
            </pre>
          )}
        </div>

        <div>
          <label htmlFor="llm-api-base" className="text-sm font-medium">API Base</label>
          <Input
            id="llm-api-base"
            value={apiBase}
            onChange={(e) => setApiBase(e.target.value)}
            placeholder="Leave empty for default"
          />
        </div>

        <div>
          <label htmlFor="llm-api-key" className="text-sm font-medium">API Key</label>
          <div className="flex gap-2">
            <Input
              id="llm-api-key"
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Leave empty for env var or local providers"
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
          <p className="text-xs text-muted-foreground mt-1">
            Stored in settings.yaml. Can also be set via environment variable (e.g. OPENAI_API_KEY).
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
              <TooltipContent side="bottom" className="max-w-64">
                {customMode
                  ? "Switch back to picking a model from the dropdown list."
                  : "Type a LiteLLM model ID directly, e.g. openai/gpt-4o. For OpenAI-compatible APIs (Venice, Together, etc.) use openai/<model-name> with a custom API Base."}
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

        <div className="border-t pt-4 mt-4 space-y-4">
          <h4 className="text-sm font-medium">Generation Parameters</h4>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm text-muted-foreground">Temperature</label>
              <span className="text-sm font-mono w-12 text-right">{temperature.toFixed(2)}</span>
            </div>
            <Slider
              value={[temperature]}
              min={0}
              max={2}
              step={0.05}
              onValueChange={([v]) => { setTemperature(v); setParamsDirty(true) }}
            />
            <p className="text-xs text-muted-foreground">
              Lower = more focused, higher = more creative. Default: 0.30
            </p>
          </div>

          <div className="space-y-1">
            <label htmlFor="llm-max-tokens" className="text-sm text-muted-foreground">Max Output Tokens</label>
            <Input
              id="llm-max-tokens"
              type="number"
              min={1}
              max={128000}
              value={maxTokens}
              onChange={(e) => { setMaxTokens(Number(e.target.value)); setParamsDirty(true) }}
            />
            <p className="text-xs text-muted-foreground">
              Maximum tokens in the LLM response.
              {modelInfo?.max_output_tokens != null && (
                <> Model supports up to <strong>{(modelInfo.max_output_tokens / 1000).toFixed(0)}K</strong>.</>
              )}
            </p>
          </div>

          {isOllama && (
            <div className="space-y-1">
              <label htmlFor="llm-num-ctx" className="text-sm text-muted-foreground">Context Window (num_ctx)</label>
              <Input
                id="llm-num-ctx"
                type="number"
                min={1024}
                max={1048576}
                value={numCtx}
                onChange={(e) => { setNumCtx(e.target.value); setParamsDirty(true) }}
                placeholder="Model default"
              />
              <p className="text-xs text-muted-foreground">
                Ollama context window size. Leave empty for model default (usually 2048-4096).
                Set higher (e.g. 32768) for longer documents.
              </p>
            </div>
          )}

          <Button
            size="sm"
            disabled={!paramsDirty}
            onClick={async () => {
              const ctx = numCtx ? Number(numCtx) : null
              await onSaveLlmParams(temperature, maxTokens, ctx)
              setParamsDirty(false)
            }}
          >
            Save Parameters
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
