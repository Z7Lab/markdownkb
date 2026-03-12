import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import type { ModelInfo } from "@/lib/types"

export function GenerationParams({
  initialTemperature,
  initialMaxTokens,
  initialNumCtx,
  isOllama,
  modelInfo,
  onSave,
}: {
  initialTemperature: number
  initialMaxTokens: number
  initialNumCtx: number | null
  isOllama: boolean
  modelInfo: ModelInfo | null
  onSave: (temperature: number, maxTokens: number, numCtx: number | null) => Promise<void>
}) {
  const [temperature, setTemperature] = useState(initialTemperature)
  const [maxTokens, setMaxTokens] = useState(initialMaxTokens)
  const [numCtx, setNumCtx] = useState<string>(initialNumCtx?.toString() ?? "")
  const [dirty, setDirty] = useState(false)

  return (
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
          onValueChange={([v]) => { setTemperature(v); setDirty(true) }}
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
          onChange={(e) => { setMaxTokens(Number(e.target.value)); setDirty(true) }}
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
            onChange={(e) => { setNumCtx(e.target.value); setDirty(true) }}
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
