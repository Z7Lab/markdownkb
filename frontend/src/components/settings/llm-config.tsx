import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
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
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ChevronDown, HelpCircle } from "lucide-react"
import type { AppSettings, ModelInfo } from "@/lib/types"

interface TestMeta {
  model: string
  time_seconds: number
  chunks?: number
}

export function LlmConfig({
  settings,
  providerStatus,
  modelStatus,
  onSave,
  onTestProvider,
  onPingModel,
  onRefreshModels,
  onFetchModelInfo,
}: {
  settings: AppSettings
  providerStatus: string
  modelStatus: string
  onSave: (name: string, model: string, apiBase: string) => Promise<void>
  onTestProvider: (name: string, model: string, apiBase: string) => Promise<void>
  onPingModel: (model: string, apiBase: string, signal?: AbortSignal) => Promise<void>
  onRefreshModels: (name: string, apiBase: string) => Promise<{ models: string[]; status: string }>
  onFetchModelInfo: (model: string, apiBase: string) => Promise<ModelInfo>
}) {
  const [provider, setProvider] = useState(settings.active_provider)
  const [model, setModel] = useState(settings.active_model)
  const [apiBase, setApiBase] = useState(settings.active_api_base)
  const [models, setModels] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [customMode, setCustomMode] = useState(false)

  // Track whether the user has explicitly changed model (prevents auto-override)
  const userPickedModel = useRef(false)

  // Model info
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null)
  const [infoLoading, setInfoLoading] = useState(false)

  // Ping model
  const [pingLoading, setPingLoading] = useState(false)
  const pingAbortRef = useRef<AbortController | null>(null)

  // Test prompt (streaming)
  const [testOpen, setTestOpen] = useState(false)
  const [testPromptText, setTestPromptText] = useState("")
  const [testResponse, setTestResponse] = useState("")
  const [testMeta, setTestMeta] = useState<TestMeta | null>(null)
  const [testLoading, setTestLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const outputRef = useRef<HTMLPreElement>(null)

  // Auto-fetch models on mount and when provider/apiBase changes
  useEffect(() => {
    let cancelled = false
    async function fetchModels() {
      setLoading(true)
      try {
        const res = await onRefreshModels(provider, apiBase)
        if (!cancelled && res.models.length > 0) {
          setModels(res.models)
          setCustomMode(false)
        }
      } catch {
        // silently fail — user can still type custom model
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    // Reset the user-picked flag when provider changes
    userPickedModel.current = false
    fetchModels()
    return () => { cancelled = true }
  }, [provider, apiBase, onRefreshModels])

  // Fetch model info when model changes (debounced)
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
        setModels(res.models)
        // Only auto-select first model if user hasn't explicitly picked one
        // or their pick isn't in the new list
        if (!userPickedModel.current && !res.models.includes(model)) {
          setModel(res.models[0])
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
      await onPingModel(model, apiBase, controller.signal)
    } finally {
      setPingLoading(false)
    }
  }

  function handleCancelPing() {
    pingAbortRef.current?.abort()
    pingAbortRef.current = null
    setPingLoading(false)
  }

  async function handleTestPrompt() {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    // Capture current values at time of click
    const targetModel = model
    const targetApiBase = apiBase
    const targetProvider = provider

    setTestLoading(true)
    setTestResponse("")
    setTestMeta(null)

    try {
      const res = await fetch("/api/settings/test-prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: testPromptText,
          provider: targetProvider,
          model: targetModel,
          api_base: targetApiBase,
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const text = await res.text()
        setTestResponse(`Error: ${res.status} ${text}`)
        setTestLoading(false)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) { setTestLoading(false); return }

      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() ?? ""

        let eventType = ""
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7)
          } else if (line.startsWith("data: ")) {
            const data = JSON.parse(line.slice(6))
            if (eventType === "token") {
              setTestResponse((prev) => prev + data.content)
              if (outputRef.current) {
                outputRef.current.scrollTop = outputRef.current.scrollHeight
              }
            } else if (eventType === "meta" || eventType === "done") {
              setTestMeta(data)
            } else if (eventType === "error") {
              setTestResponse((prev) => prev + `\nError: ${data.message}`)
            }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setTestResponse((prev) => prev + `\nError: ${err}`)
      }
    } finally {
      setTestLoading(false)
    }
  }

  function handleStopTest() {
    abortRef.current?.abort()
    abortRef.current = null
    setTestLoading(false)
  }

  // Build deduped options: fetched models + current model if not in list
  const selectOptions = [...models]
  if (model && !models.includes(model)) {
    selectOptions.unshift(model)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>LLM Configuration</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="text-sm font-medium">Provider</label>
          <div className="flex gap-2">
            <Select value={provider} onValueChange={onProviderChange}>
              <SelectTrigger className="flex-1">
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
            <Button variant="outline" size="sm" onClick={() => onTestProvider(provider, model, apiBase)}>
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
          <label className="text-sm font-medium">API Base</label>
          <Input
            value={apiBase}
            onChange={(e) => setApiBase(e.target.value)}
            placeholder="Leave empty for default"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Model</label>
          <div className="flex gap-2">
            {customMode ? (
              <Input
                value={model}
                onChange={(e) => { userPickedModel.current = true; setModel(e.target.value) }}
                className="flex-1"
                placeholder="e.g. anthropic/claude-3-5-sonnet-20241022"
                autoFocus
              />
            ) : (
              <Select value={model} onValueChange={onModelChange}>
                <SelectTrigger className="flex-1" disabled={loading}>
                  <SelectValue placeholder={loading ? "Loading models..." : "Select model"} />
                </SelectTrigger>
                <SelectContent>
                  {selectOptions.map((m) => (
                    <SelectItem key={m} value={m}>{m}</SelectItem>
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
                  : "Type a LiteLLM model ID directly, e.g. anthropic/claude-3-5-sonnet-20241022 or openai/gpt-4o. Useful for models not in the list."}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {/* Model info card */}
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
          <Button onClick={() => onSave(provider, model, apiBase)}>
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

        {/* Test Prompt section */}
        <Collapsible open={testOpen} onOpenChange={setTestOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="w-full justify-between">
              <span>
                Test Prompt
                <span className="ml-2 text-xs text-muted-foreground font-normal">{model}</span>
              </span>
              <ChevronDown className={`h-4 w-4 transition-transform ${testOpen ? "rotate-180" : ""}`} />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-3 pt-2">
            <Textarea
              value={testPromptText}
              onChange={(e) => setTestPromptText(e.target.value)}
              placeholder="Enter a test prompt (raw, no RAG)..."
              rows={3}
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleTestPrompt} disabled={testLoading || !testPromptText.trim()}>
                Send
              </Button>
              {testLoading && (
                <Button size="sm" variant="secondary" onClick={handleStopTest}>
                  Stop
                </Button>
              )}
            </div>
            {(testResponse || testLoading) && (
              <div className="space-y-2">
                <pre
                  ref={outputRef}
                  className="text-sm bg-muted p-3 rounded-md whitespace-pre-wrap max-h-64 overflow-auto"
                >
                  {testResponse || (testLoading ? "" : "")}
                  {testLoading && <span className="animate-pulse">|</span>}
                </pre>
                {testMeta && (
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    <span>Model: {testMeta.model}</span>
                    <span>Time: {testMeta.time_seconds}s</span>
                    {testMeta.chunks != null && <span>Chunks: {testMeta.chunks}</span>}
                  </div>
                )}
              </div>
            )}
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  )
}
