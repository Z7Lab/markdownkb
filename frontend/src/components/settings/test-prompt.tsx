import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { ChevronDown } from "lucide-react"
import { parseSSEStream } from "@/lib/sse"

interface TestMeta {
  model: string
  time_seconds: number
  chunks?: number
}

export function TestPrompt({
  provider,
  model,
  apiBase,
  apiKey,
}: {
  provider: string
  model: string
  apiBase: string
  apiKey: string
}) {
  const [open, setOpen] = useState(false)
  const [promptText, setPromptText] = useState("")
  const [response, setResponse] = useState("")
  const [meta, setMeta] = useState<TestMeta | null>(null)
  const [loading, setLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const outputRef = useRef<HTMLPreElement>(null)

  async function handleSend() {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setResponse("")
    setMeta(null)

    try {
      const res = await fetch("/api/v1/settings/test-prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: promptText,
          provider,
          model,
          api_base: apiBase,
          api_key: apiKey,
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const text = await res.text()
        setResponse(`Error: ${res.status} ${text}`)
        setLoading(false)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) { setLoading(false); return }

      await parseSSEStream(reader, (event, data) => {
        if (event === "token") {
          setResponse((prev) => prev + (data.content as string))
          if (outputRef.current) {
            outputRef.current.scrollTop = outputRef.current.scrollHeight
          }
        } else if (event === "meta" || event === "done") {
          setMeta(data as unknown as TestMeta)
        } else if (event === "error") {
          setResponse((prev) => prev + `\nError: ${data.message}`)
        }
      })
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setResponse((prev) => prev + `\nError: ${err}`)
      }
    } finally {
      setLoading(false)
    }
  }

  function handleStop() {
    abortRef.current?.abort()
    abortRef.current = null
    setLoading(false)
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <Button variant="ghost" size="sm" className="w-full justify-between">
          <span>
            Test Prompt
            <span className="ml-2 text-xs text-muted-foreground font-normal">{model}</span>
          </span>
          <ChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-3 pt-2">
        <Textarea
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          placeholder="Enter a test prompt (raw, no RAG)..."
          rows={3}
        />
        <div className="flex gap-2">
          <Button size="sm" onClick={handleSend} disabled={loading || !promptText.trim()}>
            Send
          </Button>
          {loading && (
            <Button size="sm" variant="secondary" onClick={handleStop}>
              Stop
            </Button>
          )}
        </div>
        {(response || loading) && (
          <div className="space-y-2">
            <pre
              ref={outputRef}
              className="text-sm bg-muted p-3 rounded-md whitespace-pre-wrap max-h-64 overflow-auto"
            >
              {response || (loading ? "" : "")}
              {loading && <span className="animate-pulse">|</span>}
            </pre>
            {meta && (
              <div className="flex gap-4 text-xs text-muted-foreground">
                <span>Model: {meta.model}</span>
                <span>Time: {meta.time_seconds}s</span>
                {meta.chunks != null && <span>Chunks: {meta.chunks}</span>}
              </div>
            )}
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  )
}
