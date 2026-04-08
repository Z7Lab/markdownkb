import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Cpu, Terminal, ExternalLink, ChevronDown, ChevronUp, Copy, Check } from "lucide-react"

type Platform = "macos" | "linux" | "windows"
type Provider = "ollama" | "llamacpp" | "cloud" | "custom"

function detectPlatform(): Platform {
  const ua = navigator.userAgent.toLowerCase()
  if (ua.includes("mac")) return "macos"
  if (ua.includes("win")) return "windows"
  return "linux"
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
      onClick={() => {
        navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      }}
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

function CodeBlock({ children }: { children: string }) {
  return (
    <div className="relative">
      <pre className="bg-muted rounded-md px-3 py-2 text-xs font-mono overflow-x-auto">
        {children}
      </pre>
      <CopyButton text={children} />
    </div>
  )
}

// ── Ollama Guide ──────────────────────────────────

const OLLAMA_INSTALL: Record<Platform, { label: string; command?: string; link?: string }> = {
  macos: { label: "macOS", command: "brew install ollama", link: "https://ollama.com/download/mac" },
  linux: { label: "Linux", command: "curl -fsSL https://ollama.com/install.sh | sh" },
  windows: { label: "Windows", link: "https://ollama.com/download/windows" },
}

const OLLAMA_MODELS = [
  { name: "qwen3:8b", size: "5 GB", desc: "General purpose, multilingual, good reasoning" },
  { name: "llama3.1:8b", size: "5 GB", desc: "English-focused, strong instruction following" },
  { name: "gemma3:4b", size: "3 GB", desc: "Lightweight, fast on low-memory machines" },
]

function OllamaGuide({ expanded, onNavigateSettings, hideSettingsButton }: { expanded: boolean; onNavigateSettings: () => void; hideSettingsButton?: boolean }) {
  const [platform, setPlatform] = useState<Platform>(detectPlatform)
  const step = OLLAMA_INSTALL[platform]

  return (
    <div className="space-y-4">
      {/* Step 1: Install */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">1</Badge>
          <span className="text-sm font-medium">Install Ollama</span>
          <div className="flex gap-1 ml-auto">
            {(Object.entries(OLLAMA_INSTALL) as [Platform, typeof step][]).map(([key, s]) => (
              <Button
                key={key}
                variant={platform === key ? "default" : "outline"}
                size="sm"
                className="h-6 text-xs px-2"
                onClick={() => setPlatform(key)}
              >
                {s.label}
              </Button>
            ))}
          </div>
        </div>
        {step.command && <CodeBlock>{step.command}</CodeBlock>}
        {step.link && (
          <a
            href={step.link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
          >
            {step.command ? "Or download from ollama.com" : "Download from ollama.com"}
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>

      {/* Step 2: Pull a model */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">2</Badge>
          <span className="text-sm font-medium">Pull a model</span>
        </div>
        <CodeBlock>ollama pull qwen3:8b</CodeBlock>
        {expanded && (
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">Other options:</p>
            <div className="grid gap-1">
              {OLLAMA_MODELS.map((m) => (
                <div key={m.name} className="flex items-center gap-2 text-xs">
                  <code className="bg-muted px-1.5 py-0.5 rounded font-mono">{m.name}</code>
                  <span className="text-muted-foreground">{m.size}</span>
                  <span className="text-muted-foreground">— {m.desc}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Step 3: Configure */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">3</Badge>
          <span className="text-sm font-medium">Configure mdkb</span>
        </div>
        {hideSettingsButton ? (
          <p className="text-xs text-muted-foreground">
            Set the API base above, click <strong>Refresh</strong> to load your models, then <strong>Save</strong>.
          </p>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">
              Go to Settings &gt; Chat Model, select <strong>ollama</strong>, and your pulled models will appear.
              You can also pull models directly from the Settings UI.
            </p>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={onNavigateSettings}>
              <Terminal className="h-3.5 w-3.5" />
              Open Settings
            </Button>
          </>
        )}
      </div>

      {expanded && (
        <>
          <div className="rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 p-3 space-y-1">
            <p className="text-xs font-medium">Docker users</p>
            <p className="text-xs text-muted-foreground">
              Ollama runs on your host machine, not inside the container.
              Set the API base to <code className="bg-muted px-1 rounded">http://host.docker.internal:11434</code> in Settings.
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium">Troubleshooting</p>
            <ul className="text-xs text-muted-foreground space-y-1 list-disc pl-4">
              <li>Check Ollama is running: <code className="bg-muted px-1 rounded">ollama list</code></li>
              <li>Verify the port: <code className="bg-muted px-1 rounded">curl http://localhost:11434/api/tags</code></li>
              <li>Docker users: use <code className="bg-muted px-1 rounded">host.docker.internal</code> not <code className="bg-muted px-1 rounded">localhost</code></li>
            </ul>
          </div>
        </>
      )}
    </div>
  )
}

// ── llama.cpp Guide ───────────────────────────────

function LlamaCppGuide({ expanded, onNavigateSettings, hideSettingsButton }: { expanded: boolean; onNavigateSettings: () => void; hideSettingsButton?: boolean }) {
  const [platform, setPlatform] = useState<Platform>(detectPlatform)

  return (
    <div className="space-y-4">
      {/* Step 1: Install */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">1</Badge>
          <span className="text-sm font-medium">Build llama.cpp</span>
          <div className="flex gap-1 ml-auto">
            {(["linux", "macos", "windows"] as Platform[]).map((key) => (
              <Button
                key={key}
                variant={platform === key ? "default" : "outline"}
                size="sm"
                className="h-6 text-xs px-2"
                onClick={() => setPlatform(key)}
              >
                {key === "macos" ? "macOS" : key === "linux" ? "Linux" : "Windows"}
              </Button>
            ))}
          </div>
        </div>
        {platform === "windows" ? (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              Download a pre-built release from GitHub, or build from source with CMake and Visual Studio.
            </p>
            <a
              href="https://github.com/ggerganov/llama.cpp/releases"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
            >
              Download from GitHub Releases
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        ) : (
          <>
            <CodeBlock>{platform === "macos"
              ? "brew install cmake\ngit clone https://github.com/ggerganov/llama.cpp.git\ncd llama.cpp\ncmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON\ncmake --build build --target llama-server -j$(sysctl -n hw.ncpu)"
              : "sudo apt-get install -y build-essential cmake git\ngit clone https://github.com/ggerganov/llama.cpp.git\ncd llama.cpp\ncmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON\ncmake --build build --target llama-server -j$(nproc)"
            }</CodeBlock>
            <p className="text-xs text-muted-foreground">
              <code className="bg-muted px-1 rounded">GGML_NATIVE=ON</code> enables CPU-specific optimizations (AVX2, AVX512) for best performance.
            </p>
          </>
        )}
      </div>

      {/* Step 2: Download a model */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">2</Badge>
          <span className="text-sm font-medium">Download a GGUF model</span>
        </div>
        <p className="text-xs text-muted-foreground">
          Download a quantized GGUF model from{" "}
          <a
            href="https://huggingface.co/models?sort=trending&search=gguf"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            HuggingFace
            <ExternalLink className="inline h-2.5 w-2.5 ml-0.5" />
          </a>
          . Look for <code className="bg-muted px-1 rounded">Q4_K_M</code> quantizations — good balance of speed and quality.
        </p>
        {expanded && (
          <div className="grid gap-1">
            {[
              { name: "Qwen3-8B-Q4_K_M", size: "5 GB", desc: "General purpose, multilingual" },
              { name: "Llama-3.1-8B-Q4_K_M", size: "5 GB", desc: "English-focused, instruction following" },
              { name: "Gemma-3-4B-Q4_K_M", size: "3 GB", desc: "Lightweight, fast" },
            ].map((m) => (
              <div key={m.name} className="flex items-center gap-2 text-xs">
                <code className="bg-muted px-1.5 py-0.5 rounded font-mono">{m.name}.gguf</code>
                <span className="text-muted-foreground">{m.size}</span>
                <span className="text-muted-foreground">— {m.desc}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Step 3: Start the server */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">3</Badge>
          <span className="text-sm font-medium">Start llama-server</span>
        </div>
        <CodeBlock>{`~/llama.cpp/build/bin/llama-server \\
  -m /path/to/model.gguf \\
  --host 127.0.0.1 --port 8080 \\
  -t 6 -c 2048 -fa on`}</CodeBlock>
        {expanded && (
          <div className="grid gap-1 text-xs text-muted-foreground">
            <span><code className="bg-muted px-1 rounded">-t 6</code> — threads (use CPU cores - 2)</span>
            <span><code className="bg-muted px-1 rounded">-c 2048</code> — context size (increase for longer conversations)</span>
            <span><code className="bg-muted px-1 rounded">-fa on</code> — flash attention (faster, less memory)</span>
          </div>
        )}
      </div>

      {/* Step 4: Configure mdkb */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">4</Badge>
          <span className="text-sm font-medium">Configure mdkb</span>
        </div>
        {hideSettingsButton ? (
          <p className="text-xs text-muted-foreground">
            Set the API base to <code className="bg-muted px-1 rounded">http://localhost:8080/v1</code> above, click <strong>Refresh</strong> to detect your model, then <strong>Save</strong>.
          </p>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">
              Go to Settings &gt; Chat Model and add a provider with:
            </p>
            <div className="grid gap-1 text-xs">
              <span>Provider name: <code className="bg-muted px-1 rounded">llamacpp</code></span>
              <span>API base: <code className="bg-muted px-1 rounded">http://localhost:8080/v1</code></span>
              <span>Model: the name shown by <code className="bg-muted px-1 rounded">curl http://localhost:8080/v1/models</code></span>
            </div>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={onNavigateSettings}>
              <Terminal className="h-3.5 w-3.5" />
              Open Settings
            </Button>
          </>
        )}
      </div>

      {expanded && (
        <>
          <div className="rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 p-3 space-y-1">
            <p className="text-xs font-medium">Docker users</p>
            <p className="text-xs text-muted-foreground">
              llama-server runs on your host. Set the API base
              to <code className="bg-muted px-1 rounded">http://host.docker.internal:8080/v1</code> in Settings.
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium">Why llama.cpp?</p>
            <ul className="text-xs text-muted-foreground space-y-1 list-disc pl-4">
              <li>Lower memory than Ollama (~3.5 GB vs ~5.2 GB for same model)</li>
              <li>Native CPU optimizations compiled for your specific hardware</li>
              <li>Full control over inference parameters</li>
              <li>No wrapper overhead</li>
            </ul>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium">Troubleshooting</p>
            <ul className="text-xs text-muted-foreground space-y-1 list-disc pl-4">
              <li>Check server: <code className="bg-muted px-1 rounded">curl http://localhost:8080/health</code></li>
              <li>Verify models: <code className="bg-muted px-1 rounded">curl http://localhost:8080/v1/models</code></li>
              <li>First request may be slow (model loading into RAM)</li>
            </ul>
          </div>
        </>
      )}
    </div>
  )
}

// ── Cloud API Guide ───────────────────────────────

function CloudGuide({ expanded, onNavigateSettings, hideSettingsButton }: { expanded: boolean; onNavigateSettings: () => void; hideSettingsButton?: boolean }) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">1</Badge>
          <span className="text-sm font-medium">Get an API key</span>
        </div>
        <p className="text-xs text-muted-foreground">
          Sign up with a provider and create an API key:
        </p>
        <div className="grid gap-1">
          {[
            { name: "Anthropic", url: "https://console.anthropic.com/", models: "Claude 4.5, Claude 4" },
            { name: "OpenAI", url: "https://platform.openai.com/api-keys", models: "GPT-4o, GPT-4.1" },
            { name: "Venice", url: "https://venice.ai/", models: "Private inference, no data retention" },
            { name: "Together", url: "https://api.together.xyz/", models: "Open source models hosted" },
          ].map((p) => (
            <div key={p.name} className="flex items-center gap-2 text-xs">
              <a
                href={p.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 dark:text-blue-400 hover:underline font-medium inline-flex items-center gap-0.5"
              >
                {p.name}
                <ExternalLink className="h-2.5 w-2.5" />
              </a>
              <span className="text-muted-foreground">— {p.models}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">2</Badge>
          <span className="text-sm font-medium">Configure mdkb</span>
        </div>
        {hideSettingsButton ? (
          <p className="text-xs text-muted-foreground">
            Enter your API key and API base above, click <strong>Refresh</strong> to load models, then <strong>Save</strong>.
          </p>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">
              Go to Settings &gt; Chat Model, set the provider name, model, API base, and paste your API key.
            </p>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={onNavigateSettings}>
              <Terminal className="h-3.5 w-3.5" />
              Open Settings
            </Button>
          </>
        )}
      </div>

      {expanded && (
        <div className="space-y-1">
          <p className="text-xs font-medium">API key storage</p>
          <p className="text-xs text-muted-foreground">
            For production, store keys in <code className="bg-muted px-1 rounded">secrets/</code> files
            or environment variables rather than entering them in the UI.
            Keys entered in Settings are stored in the settings file.
          </p>
        </div>
      )}
    </div>
  )
}

function CustomGuide({ expanded, onNavigateSettings, hideSettingsButton }: { expanded: boolean; onNavigateSettings: () => void; hideSettingsButton?: boolean }) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Any server that exposes an OpenAI-compatible <code className="bg-muted px-1 rounded">/v1/chat/completions</code> endpoint works with mdkb.
      </p>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">1</Badge>
          <span className="text-sm font-medium">Start your server</span>
        </div>
        <div className="grid gap-1.5">
          {[
            { name: "LM Studio", port: "1234", url: "https://lmstudio.ai/", desc: "GUI app, download models from UI, one-click server" },
            { name: "vLLM", port: "8000", url: "https://docs.vllm.ai/", desc: "Production-grade, GPU-optimized, high throughput" },
            { name: "llama.cpp", port: "8080", url: "", desc: "Lightweight, CPU-optimized (see llama.cpp tab for build guide)" },
            { name: "text-generation-webui", port: "5000", url: "https://github.com/oobabooga/text-generation-webui", desc: "Feature-rich UI with API mode" },
          ].map((s) => (
            <div key={s.name} className="flex items-start gap-2 text-xs">
              {s.url ? (
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 dark:text-blue-400 hover:underline font-medium shrink-0 inline-flex items-center gap-0.5"
                >
                  {s.name}
                  <ExternalLink className="h-2.5 w-2.5" />
                </a>
              ) : (
                <span className="font-medium shrink-0">{s.name}</span>
              )}
              <span className="text-muted-foreground">
                (port {s.port}) — {s.desc}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">2</Badge>
          <span className="text-sm font-medium">Configure mdkb</span>
        </div>
        {hideSettingsButton ? (
          <>
            <p className="text-xs text-muted-foreground">
              Set the API base above to your server's URL (e.g. <code className="bg-muted px-1 rounded">http://localhost:1234/v1</code> for LM Studio),
              click <strong>Refresh</strong> to detect models, then <strong>Save</strong>.
            </p>
            <p className="text-xs text-muted-foreground">
              Most local servers don't need an API key. If yours does, enter it in the API Key field.
            </p>
          </>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">
              Go to Settings &gt; Chat Model, select <strong>Custom</strong>, set the API base to your server URL, and click Refresh.
            </p>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={onNavigateSettings}>
              <Terminal className="h-3.5 w-3.5" />
              Open Settings
            </Button>
          </>
        )}
      </div>

      {expanded && (
        <div className="rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 p-3 space-y-1">
          <p className="text-xs font-medium">Docker users</p>
          <p className="text-xs text-muted-foreground">
            If the server runs on your host machine, use <code className="bg-muted px-1 rounded">http://host.docker.internal:PORT/v1</code> as the API base.
          </p>
        </div>
      )}
    </div>
  )
}

// ── Main Component ────────────────────────────────

const PROVIDERS: { key: Provider; label: string; desc: string }[] = [
  { key: "ollama", label: "Ollama", desc: "Easiest — one command install, model management built in" },
  { key: "llamacpp", label: "llama.cpp", desc: "Lower memory, native CPU optimizations, full control" },
  { key: "cloud", label: "Cloud API", desc: "Anthropic, Venice, or other hosted providers" },
  { key: "custom", label: "Custom", desc: "LM Studio, vLLM, OpenAI, or any OpenAI-compatible server" },
]

export function LlmSetupGuide({
  onNavigateSettings,
  initialProvider,
  embedded,
}: {
  onNavigateSettings: () => void
  initialProvider?: Provider
  /** When embedded in Settings, hide redundant "Open Settings" buttons and provider tabs */
  embedded?: boolean
}) {
  const [provider, setProvider] = useState<Provider>(initialProvider ?? "ollama")
  const [expanded, setExpanded] = useState(false)

  // Sync when parent changes the initial provider (e.g. dropdown switch)
  useEffect(() => {
    if (initialProvider) setProvider(initialProvider)
  }, [initialProvider])

  return (
    <Card className="border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Cpu className="h-4 w-4" />
            Get Started with an LLM
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            className="gap-1 text-xs"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {expanded ? "Less" : "More"}
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">
          mdkb needs an LLM for chat, search summaries, and planning.
          Choose a provider to get started:
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Provider tabs — hidden when embedded in Settings since dropdown controls this */}
        {!embedded && (
          <>
            <div className="flex gap-2">
              {PROVIDERS.map((p) => (
                <Button
                  key={p.key}
                  variant={provider === p.key ? "default" : "outline"}
                  size="sm"
                  className="text-xs"
                  onClick={() => setProvider(p.key)}
                >
                  {p.label}
                </Button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              {PROVIDERS.find((p) => p.key === provider)?.desc}
            </p>
          </>
        )}

        {/* Provider-specific guide */}
        {provider === "ollama" && <OllamaGuide expanded={expanded} onNavigateSettings={onNavigateSettings} hideSettingsButton={embedded} />}
        {provider === "llamacpp" && <LlamaCppGuide expanded={expanded} onNavigateSettings={onNavigateSettings} hideSettingsButton={embedded} />}
        {provider === "cloud" && <CloudGuide expanded={expanded} onNavigateSettings={onNavigateSettings} hideSettingsButton={embedded} />}
        {provider === "custom" && <CustomGuide expanded={expanded} onNavigateSettings={onNavigateSettings} hideSettingsButton={embedded} />}

        {/* Embeddings note — applies to all providers */}
        <div className="border-t pt-4 space-y-1.5">
          <p className="text-xs font-medium">About embeddings</p>
          <p className="text-xs text-muted-foreground">
            Embeddings power search and document indexing — they're <strong>separate</strong> from the chat model.
            mdkb ships with a local ONNX embedding model that runs on CPU with no setup needed.
            You can optionally switch to Ollama or any OpenAI-compatible embedding API
            in Settings &gt; Embedding Model.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
