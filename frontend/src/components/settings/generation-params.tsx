import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import type { ModelInfo } from "@/lib/types"

export function GenerationParams({
  initialTemperature,
  initialMaxTokens,
  initialNumCtx,
  isOllama,
  isCloud,
  modelInfo,
  onSave,
}: {
  initialTemperature: number
  initialMaxTokens: number
  initialNumCtx: number | null
  isOllama: boolean
  /** True for cloud APIs (Anthropic, Venice, OpenAI) where only max_tokens matters */
  isCloud: boolean
  modelInfo: ModelInfo | null
  onSave: (temperature: number, maxTokens: number, numCtx: number | null) => Promise<void>
}) {
  const [temperature, setTemperature] = useState(initialTemperature)
  const [maxTokens, setMaxTokens] = useState(initialMaxTokens)
  const [numCtx, setNumCtx] = useState<string>(initialNumCtx?.toString() ?? "")
  const [dirty, setDirty] = useState(false)

  // Reset values when provider changes (initialMaxTokens/initialNumCtx change)
  useEffect(() => {
    setTemperature(initialTemperature)
    setMaxTokens(initialMaxTokens)
    setNumCtx(initialNumCtx?.toString() ?? "")
    setDirty(false)
  }, [initialTemperature, initialMaxTokens, initialNumCtx])

  const numCtxVal = numCtx ? Number(numCtx) : null
  const ctxWarning = isOllama && numCtxVal && maxTokens > numCtxVal
    ? `max_tokens (${maxTokens}) exceeds context window (${numCtxVal}). Output will be truncated.`
    : null

  return (
    <div className="border-t pt-4 mt-4 space-y-4">
      <h4 className="text-sm font-medium">Generation Parameters</h4>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span id="gen-temperature-label" className="text-sm text-muted-foreground">Temperature</span>
          <span className="text-sm font-mono w-12 text-right">{temperature.toFixed(2)}</span>
        </div>
        <Slider
          value={[temperature]}
          min={0}
          max={2}
          step={0.05}
          onValueChange={([v]) => { if (v !== undefined) { setTemperature(v); setDirty(true) } }}
          aria-labelledby="gen-temperature-label"
        />
        <p className="text-xs text-muted-foreground">
          Lower = more focused, higher = more creative. Default: 0.30
        </p>
      </div>

      <div className="space-y-1">
        <label htmlFor="llm-max-tokens" className="text-sm text-muted-foreground">
          Max Output Tokens
        </label>
        <Input
          id="llm-max-tokens"
          type="number"
          min={1}
          max={128000}
          value={maxTokens}
          onChange={(e) => { const v = Number(e.target.value); if (v >= 1) { setMaxTokens(v); setDirty(true) } }}
        />
        <p className="text-xs text-muted-foreground">
          {isOllama ? (
            <>Maximum tokens in the response. Must fit within the context window (num_ctx) along with the input.</>
          ) : (
            <>Maximum tokens in the LLM response.</>
          )}
          {modelInfo?.max_output_tokens != null && (
            <> Model supports up to <strong>{(modelInfo.max_output_tokens / 1000).toFixed(0)}K</strong> output tokens.</>
          )}
        </p>
      </div>

      {isOllama && (
        <div className="space-y-1">
          <label htmlFor="llm-num-ctx" className="text-sm text-muted-foreground">
            Context Window (num_ctx)
          </label>
          <Input
            id="llm-num-ctx"
            type="number"
            min={1024}
            max={1048576}
            value={numCtx}
            onChange={(e) => { setNumCtx(e.target.value); setDirty(true) }}
            placeholder="Model default"
          />
          <p className="text-xs text-muted-foreground">
            Total context size for Ollama — includes both input (your documents + conversation) and output (the response).
            Leave empty for model default. Set higher (e.g. 8192 or 32768) for longer conversations and more document context.
            More context = more RAM usage.
          </p>
          {ctxWarning && (
            <p className="text-xs text-amber-600">{ctxWarning}</p>
          )}
        </div>
      )}

      {!isOllama && !isCloud && (
        <p className="text-xs text-muted-foreground">
          For local servers (llama.cpp, LM Studio), context window is configured on the server, not here.
          Use <code className="text-[10px]">-c</code> flag for llama.cpp or the server settings in LM Studio.
        </p>
      )}

      <Button
        size="sm"
        disabled={!dirty}
        onClick={async () => {
          const ctx = numCtx ? Number(numCtx) : null
          await onSave(temperature, maxTokens, ctx)
          setDirty(false)
        }}
      >
        Save Parameters
      </Button>
    </div>
  )
}
