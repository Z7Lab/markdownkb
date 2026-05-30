import { useCallback, useEffect, useState } from "react"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
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

export function ConverterPanel() {
  const [config, setConfig] = useState<ConverterConfig>(DEFAULTS)
  const [saving, setSaving] = useState(false)
  const [loaded, setLoaded] = useState(false)

  const loadConfig = useCallback(async () => {
    try {
      const res = await api.get<ConverterConfig>("/api/v1/settings/plugins/converter")
      setConfig({ ...DEFAULTS, ...res })
      setLoaded(true)
    } catch {
      setLoaded(true)
    }
  }, [])

  useEffect(() => { loadConfig() }, [loadConfig])

  const set = (key: keyof ConverterConfig, value: boolean | string) =>
    setConfig((prev) => ({ ...prev, [key]: value }))

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put("/api/v1/settings/plugins/converter", config)
      toast.success("File Converter settings saved")
    } catch (err) {
      toast.error(`Failed to save: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

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
          <CardTitle className="text-base">Audio Transcription</CardTitle>
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

              {/* Provider selector */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Provider</label>
                <Select
                  value={config.audio_provider ?? "local"}
                  onValueChange={(v) => set("audio_provider", v)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="local">Local (faster-whisper, CPU)</SelectItem>
                    <SelectItem value="remote">Remote (OpenAI-compatible API)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Remote provider fields */}
              {config.audio_provider === "remote" && (
                <>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">API Base URL</label>
                    <Input
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
                  <div className="p-3 rounded-md bg-muted text-xs space-y-1">
                    <p className="font-medium">API key</p>
                    <p className="text-muted-foreground">
                      Set the <span className="font-mono">WHISPER_API_KEY</span> environment variable
                      or create a <span className="font-mono">whisper_api_key</span> Docker secret.
                      Keys are never stored in settings.
                    </p>
                  </div>
                </>
              )}

              {/* Local provider fields */}
              {(config.audio_provider ?? "local") === "local" && (
                <>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Model size</label>
                    <Select value={config.audio_model} onValueChange={(v) => set("audio_model", v)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {WHISPER_MODEL_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Select a size, then download it below. Requires the full image variant.
                    </p>
                  </div>

                  <Separator />
                  <WhisperModelSection activeModel={config.audio_model} />
                </>
              )}
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
