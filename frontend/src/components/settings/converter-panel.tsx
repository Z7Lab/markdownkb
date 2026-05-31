import { useCallback, useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { WhisperModelSection } from "./whisper-model-section"

interface ConverterConfig {
  web_enabled: boolean
  office_enabled: boolean
  pdf_enabled: boolean
  misc_enabled: boolean
  audio_enabled: boolean
  audio_provider: string
  audio_api_base: string
  audio_model: string
}

interface WhisperModel {
  model_size: string
  label: string
  size: string
  installed: boolean
  active: boolean
}

const DEFAULTS: ConverterConfig = {
  web_enabled: true,
  office_enabled: true,
  pdf_enabled: true,
  misc_enabled: true,
  audio_enabled: false,
  audio_provider: "local",
  audio_api_base: "",
  audio_model: "small",
}

const WHISPER_MODEL_OPTIONS = [
  { value: "tiny",     label: "Tiny (~75 MB) — fastest, lower accuracy" },
  { value: "small",    label: "Small (~244 MB) — good balance (recommended)" },
  { value: "medium",   label: "Medium (~769 MB) — higher accuracy, slower" },
  { value: "large-v2", label: "Large v2 (~1.5 GB) — best accuracy, slowest" },
  { value: "large-v3", label: "Large v3 (~1.5 GB) — latest large model" },
]

type AudioStatus = "disabled" | "not-configured" | "not-ready" | "ready"

function AudioStatusDot({ status }: { status: AudioStatus }) {
  if (status === "ready") {
    return (
      <span
        className="inline-block w-2 h-2 rounded-full bg-green-500 shrink-0"
        title="Ready"
      />
    )
  }
  if (status === "disabled") {
    return (
      <span
        className="inline-block w-2 h-2 rounded-full bg-gray-400 shrink-0"
        title="Disabled"
      />
    )
  }
  // amber for "enabled but not fully configured"
  return (
    <span
      className="inline-block w-2 h-2 rounded-full bg-amber-500 shrink-0"
      title="Enabled but not fully configured"
    />
  )
}

export function ConverterPanel() {
  const [config, setConfig] = useState<ConverterConfig>(DEFAULTS)
  const [saving, setSaving] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [savedAudioModel, setSavedAudioModel] = useState<string>(DEFAULTS.audio_model)
  const [audioModels, setAudioModels] = useState<WhisperModel[]>([])
  const [testingConnection, setTestingConnection] = useState(false)
  const [testStatus, setTestStatus] = useState<{ ok: boolean; message: string } | null>(null)

  const loadConfig = useCallback(async () => {
    try {
      const res = await api.get<{ plugin: string; config: ConverterConfig }>("/api/v1/settings/plugins/converter")
      const merged = { ...DEFAULTS, ...res.config }
      setConfig(merged)
      setSavedAudioModel(merged.audio_model)
      setLoaded(true)
    } catch {
      setLoaded(true)
    }
  }, [])

  const loadAudioModels = useCallback(async () => {
    try {
      const res = await api.get<{ models: WhisperModel[] }>("/api/v1/converter/audio/models")
      setAudioModels(res.models)
    } catch {
      // converter plugin may not be enabled yet
    }
  }, [])

  useEffect(() => { loadConfig() }, [loadConfig])
  useEffect(() => { if (loaded) loadAudioModels() }, [loaded, loadAudioModels])

  const set = (key: keyof ConverterConfig, value: boolean | string) =>
    setConfig((prev) => ({ ...prev, [key]: value }))

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put("/api/v1/settings/plugins/converter", { config })
      setSavedAudioModel(config.audio_model)
      toast.success("File Converter settings saved")
    } catch (err) {
      toast.error(`Failed to save: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleTestConnection = async () => {
    setTestingConnection(true)
    setTestStatus(null)
    try {
      const res = await api.post<{ ok: boolean; message: string }>(
        "/api/v1/converter/audio/test-remote",
        { api_base: config.audio_api_base, api_key: "" },
      )
      setTestStatus(res)
    } catch (err) {
      setTestStatus({ ok: false, message: `Error: ${(err as Error).message}` })
    } finally {
      setTestingConnection(false)
    }
  }

  // Compute status dot for the card header
  const audioStatus: AudioStatus = (() => {
    if (!config.audio_enabled) return "disabled"
    if ((config.audio_provider ?? "local") === "remote") {
      return config.audio_api_base?.trim() ? "ready" : "not-configured"
    }
    const active = audioModels.find((m) => m.model_size === config.audio_model)
    return active?.installed ? "ready" : "not-ready"
  })()

  const localActive = (config.audio_provider ?? "local") === "local"
  const remoteActive = config.audio_provider === "remote"

  if (!loaded) return <div className="p-4 text-sm text-muted-foreground">Loading...</div>

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">File Converter</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Convert documents, URLs, and audio files to markdown. Each format group can be independently
          enabled — only install the image extras you actually need.
        </p>
      </div>

      {/* Sub-converter toggles */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Format Support</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <SubConverterRow
            label="Web & YouTube"
            description="Convert URLs and YouTube videos to markdown. Full YouTube transcripts require the full image variant."
            enabled={config.web_enabled}
            onChange={(v) => set("web_enabled", v)}
          />
          <Separator />
          <SubConverterRow
            label="Office documents (DOCX, XLSX, PPTX)"
            description="Convert Word, Excel, and PowerPoint files. Requires the full image variant."
            enabled={config.office_enabled}
            onChange={(v) => set("office_enabled", v)}
          />
          <Separator />
          <SubConverterRow
            label="PDF"
            description="Text-layer extraction from PDF files. Requires the full image variant. Image-heavy PDFs yield sparse output."
            enabled={config.pdf_enabled}
            onChange={(v) => set("pdf_enabled", v)}
          />
          <Separator />
          <SubConverterRow
            label="Misc formats (HTML, EPUB, CSV, TXT, and more)"
            description="Convert HTML, EPUB, CSV, plain text, RST, RTF, ODT, Jupyter notebooks, and Outlook messages. No extra image dependencies required."
            enabled={config.misc_enabled}
            onChange={(v) => set("misc_enabled", v)}
          />
        </CardContent>
      </Card>

      {/* Audio transcription */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            Audio Transcription
            <AudioStatusDot status={audioStatus} />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <SubConverterRow
            label="Audio files (MP3, WAV, M4A, OGG, FLAC, WebM)"
            description="Transcribe audio files to markdown using local faster-whisper or a remote OpenAI-compatible API."
            enabled={config.audio_enabled}
            onChange={(v) => set("audio_enabled", v)}
          />

          {config.audio_enabled && (
            <>
              <Separator />

              {/* Two-panel provider layout */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Local CPU card */}
                <div
                  role="radio"
                  aria-checked={localActive}
                  tabIndex={0}
                  onClick={() => set("audio_provider", "local")}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") set("audio_provider", "local")
                  }}
                  className={cn(
                    "p-3 rounded-lg border-2 cursor-pointer transition-colors space-y-3",
                    localActive
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-muted-foreground/40",
                  )}
                >
                  <div className="flex items-start gap-2">
                    <div
                      className={cn(
                        "mt-0.5 w-3.5 h-3.5 rounded-full border-2 shrink-0",
                        localActive ? "border-primary bg-primary" : "border-muted-foreground",
                      )}
                    />
                    <div>
                      <p className="text-sm font-medium leading-none">Local (CPU)</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        faster-whisper · no external service
                      </p>
                    </div>
                  </div>

                  {localActive && (
                    <div
                      onClick={(e) => e.stopPropagation()}
                      className="space-y-3"
                    >
                      <div className="space-y-1.5">
                        <label className="text-xs font-medium">Model size</label>
                        <Select
                          value={config.audio_model}
                          onValueChange={(v) => set("audio_model", v)}
                        >
                          <SelectTrigger className="h-8 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {WHISPER_MODEL_OPTIONS.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value} className="text-xs">
                                {opt.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                          Select a size, then download it below. Requires the full image variant.
                        </p>
                      </div>
                      <WhisperModelSection
                        activeModel={config.audio_model}
                        saveRequired={config.audio_model !== savedAudioModel}
                        onModelsChange={setAudioModels}
                      />
                    </div>
                  )}
                </div>

                {/* Remote API card */}
                <div
                  role="radio"
                  aria-checked={remoteActive}
                  tabIndex={0}
                  onClick={() => set("audio_provider", "remote")}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") set("audio_provider", "remote")
                  }}
                  className={cn(
                    "p-3 rounded-lg border-2 cursor-pointer transition-colors space-y-3",
                    remoteActive
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-muted-foreground/40",
                  )}
                >
                  <div className="flex items-start gap-2">
                    <div
                      className={cn(
                        "mt-0.5 w-3.5 h-3.5 rounded-full border-2 shrink-0",
                        remoteActive ? "border-primary bg-primary" : "border-muted-foreground",
                      )}
                    />
                    <div>
                      <p className="text-sm font-medium leading-none">Remote API</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        OpenAI-compatible · no GPU needed
                      </p>
                    </div>
                  </div>

                  {remoteActive && (
                    <div
                      onClick={(e) => e.stopPropagation()}
                      className="space-y-3"
                    >
                      <div className="space-y-1.5">
                        <label className="text-xs font-medium">API Base URL</label>
                        <Input
                          className="h-8 text-xs"
                          placeholder="https://api.openai.com"
                          value={config.audio_api_base ?? ""}
                          onChange={(e) => set("audio_api_base", e.target.value)}
                        />
                        <p className="text-xs text-muted-foreground">
                          Any OpenAI-compatible endpoint, e.g.{" "}
                          <span className="font-mono">https://api.openai.com</span> or{" "}
                          <span className="font-mono">https://api.groq.com/openai</span>.
                        </p>
                      </div>
                      <div className="p-2.5 rounded-md bg-muted text-xs space-y-0.5">
                        <p className="font-medium">API key</p>
                        <p className="text-muted-foreground">
                          Set <span className="font-mono">WHISPER_API_KEY</span> env var or Docker secret. Keys are never stored in settings.
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs"
                          disabled={!config.audio_api_base?.trim() || testingConnection}
                          onClick={handleTestConnection}
                        >
                          {testingConnection && (
                            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                          )}
                          Test Connection
                        </Button>
                      </div>
                      {testStatus && (
                        <p
                          className={cn(
                            "text-xs px-2.5 py-1.5 rounded-md",
                            testStatus.ok
                              ? "bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-400"
                              : "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-400",
                          )}
                        >
                          {testStatus.message}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>
    </div>
  )
}

function SubConverterRow({
  label,
  description,
  enabled,
  onChange,
}: {
  label: string
  description: string
  enabled: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="space-y-0.5">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <Switch checked={enabled} onCheckedChange={onChange} className="mt-0.5 shrink-0" />
    </div>
  )
}
