import { useCallback, useEffect, useRef, useState } from "react"
import { Download, Loader2, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { api } from "@/lib/api"
import { startPolling } from "@/lib/polling"

interface WhisperModel {
  model_size: string
  label: string
  size: string
  installed: boolean
  active: boolean
}

interface InstallStatus {
  running: boolean
  progress: number
  message: string
  result: string
}

export function WhisperModelSection({
  activeModel,
  saveRequired = false,
  onModelsChange,
}: {
  activeModel: string
  saveRequired?: boolean
  onModelsChange?: (models: WhisperModel[]) => void
}) {
  const [models, setModels] = useState<WhisperModel[]>([])
  const [installing, setInstalling] = useState(false)
  const [installProgress, setInstallProgress] = useState(0)
  const [status, setStatus] = useState("")
  const [audioSupport, setAudioSupport] = useState(false)
  const pollCleanupRef = useRef<(() => void) | null>(null)

  const loadModels = useCallback(async () => {
    try {
      const res = await api.get<{ models: WhisperModel[]; audio_support: boolean }>(
        "/api/v1/converter/audio/models",
      )
      setModels(res.models)
      setAudioSupport(res.audio_support)
      onModelsChange?.(res.models)
    } catch {
      // converter plugin may not be enabled yet
    }
  // onModelsChange is intentionally excluded — callers should memoize if needed
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Check for in-progress install on mount
  useEffect(() => {
    loadModels()
    api.get<InstallStatus>("/api/v1/converter/audio/status").then((st) => {
      if (st.running) {
        setInstalling(true)
        const pct = Math.round(st.progress * 100)
        setInstallProgress(pct)
        setStatus(`[${pct}%] ${st.message}`)
        pollCleanupRef.current = startPolling("/api/v1/converter/audio/status", 1500, {
          onProgress: (s) => {
            const p = Math.round(s.progress * 100)
            setInstallProgress(p)
            setStatus(`[${p}%] ${s.message}`)
          },
          onComplete: (result) => {
            setInstalling(false)
            setInstallProgress(0)
            setStatus(result || "Install complete")
            loadModels()
          },
          onError: () => {
            setInstalling(false)
            setInstallProgress(0)
            setStatus("Lost connection during install")
          },
        })
      }
    }).catch(() => {})

    return () => { pollCleanupRef.current?.() }
  }, [loadModels])

  const handleInstall = useCallback(async (modelSize: string) => {
    setInstalling(true)
    setStatus(`Installing faster-whisper-${modelSize}...`)
    try {
      const res = await api.post<{ status: string }>("/api/v1/converter/audio/install", { model_size: modelSize })
      if (res.status === "already_installed") {
        setInstalling(false)
        setStatus(`${modelSize} already installed`)
        await loadModels()
        return
      }
      pollCleanupRef.current?.()
      pollCleanupRef.current = startPolling("/api/v1/converter/audio/status", 1000, {
        onProgress: (s) => {
          const pct = Math.round(s.progress * 100)
          setInstallProgress(pct)
          setStatus(`[${pct}%] ${s.message}`)
        },
        onComplete: (result) => {
          setInstalling(false)
          setInstallProgress(0)
          setStatus(result || `Installed ${modelSize}`)
          loadModels()
        },
        onError: () => {
          setInstalling(false)
          setInstallProgress(0)
          setStatus("Lost connection during install")
        },
      })
    } catch (e) {
      setInstalling(false)
      setStatus(`Error: ${e instanceof Error ? e.message : String(e)}`)
    }
  }, [loadModels])

  const handleUninstall = useCallback(async (modelSize: string) => {
    try {
      await api.post("/api/v1/converter/audio/uninstall", { model_size: modelSize })
      setStatus(`Removed ${modelSize}`)
      await loadModels()
    } catch (e) {
      setStatus(`Error: ${e instanceof Error ? e.message : String(e)}`)
    }
  }, [loadModels])

  if (!audioSupport) {
    return (
      <div className="space-y-2">
        <p className="text-sm font-medium">Audio Model</p>
        <p className="text-xs text-muted-foreground">
          faster-whisper is not installed in this image. Use the <code className="text-[10px]">full</code> image variant to enable audio transcription.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium">Audio Model</p>
      <p className="text-xs text-muted-foreground">
        Download the Whisper model weights once — they're cached locally and used for all transcriptions.
        The model selected above must be installed before uploading audio files.
      </p>

      {saveRequired && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          Save your settings before downloading to ensure the correct model is installed.
        </p>
      )}

      <div className="space-y-2">
        {models.map((m) => {
          const isActive = m.model_size === activeModel
          return (
            <div
              key={m.model_size}
              className={`flex items-center justify-between gap-3 p-2.5 rounded-md border text-sm ${
                isActive ? "border-primary/40 bg-primary/5" : ""
              }`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-medium">{m.label}</span>
                <span className="text-xs text-muted-foreground">{m.size}</span>
                {m.installed && isActive && <Badge className="text-xs h-4 px-1">Active</Badge>}
                {m.installed && !isActive && <Badge variant="secondary" className="text-xs h-4 px-1">Installed</Badge>}
                {!m.installed && isActive && <Badge variant="outline" className="text-xs h-4 px-1">Not downloaded</Badge>}
              </div>
              <div className="flex gap-1.5 shrink-0">
                {!m.installed && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs"
                    onClick={() => handleInstall(m.model_size)}
                    disabled={installing || saveRequired}
                    title={saveRequired ? "Save settings first" : undefined}
                  >
                    {installing && isActive ? (
                      <Loader2 className="h-3 w-3 animate-spin mr-1" />
                    ) : (
                      <Download className="h-3 w-3 mr-1" />
                    )}
                    Download
                  </Button>
                )}
                {m.installed && (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 w-7 p-0"
                    onClick={() => handleUninstall(m.model_size)}
                    disabled={installing}
                    title="Remove downloaded model"
                  >
                    <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                  </Button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {installing && (
        <Progress value={installProgress} max={100} className="h-1.5" />
      )}

      {status && (
        <p className="text-xs text-muted-foreground bg-muted px-3 py-2 rounded-md whitespace-pre-wrap">
          {status}
        </p>
      )}
    </div>
  )
}
