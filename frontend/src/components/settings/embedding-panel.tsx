import { useCallback, useState } from "react"
import { Download, FolderOpen, Loader2, RefreshCw, Square, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { api } from "@/lib/api"
import type { EmbeddingModel } from "@/lib/types"

export function EmbeddingPanel({
  models,
  activeModel,
  provider: initialProvider,
  remoteConfig: initialRemoteConfig,
  status,
  switching,
  onInstall,
  onUninstall,
  onSwitch,
  onReindex,
  onCancel,
}: {
  models: EmbeddingModel[]
  activeModel: string
  provider: string
  remoteConfig: { model: string; api_base: string; api_type: string } | null
  status: string
  switching: boolean
  onInstall: (modelId: string) => Promise<void>
  onUninstall: (modelId: string) => Promise<void>
  onSwitch: (modelId: string) => Promise<void>
  onReindex: (force?: boolean) => Promise<void>
  onCancel: () => Promise<void>
}) {
  const [confirmModel, setConfirmModel] = useState<string | null>(null)
  const [confirmReindex, setConfirmReindex] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [installing, setInstalling] = useState<string | null>(null)

  const [provider, setProvider] = useState(initialProvider || "local")
  const [remoteModel, setRemoteModel] = useState(initialRemoteConfig?.model || "nomic-embed-text")
  const [remoteApiBase, setRemoteApiBase] = useState(initialRemoteConfig?.api_base || "")
  const [remoteApiType, setRemoteApiType] = useState(initialRemoteConfig?.api_type || "ollama")
  const [testStatus, setTestStatus] = useState("")
  const [saving, setSaving] = useState(false)

  const handleSaveProvider = useCallback(async () => {
    setSaving(true)
    try {
      await api.put("/api/settings/embedding-provider", {
        provider,
        remote_model: remoteModel,
        api_base: remoteApiBase,
        api_type: remoteApiType,
      })
      setTestStatus("Saved")
    } catch (err) {
      setTestStatus(`Error: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }, [provider, remoteModel, remoteApiBase, remoteApiType])

  const handleTestRemote = useCallback(async () => {
    setTestStatus("Testing...")
    try {
      const res = await api.post<{ ok: boolean; message: string; dimensions?: number }>("/api/settings/embedding-models/test-remote", {
        model: remoteModel,
        api_base: remoteApiBase,
        api_type: remoteApiType,
      })
      setTestStatus(res.message)
    } catch (err) {
      setTestStatus(`Error: ${(err as Error).message}`)
    }
  }, [remoteModel, remoteApiBase, remoteApiType])

  async function handleInstall(modelId: string) {
    setInstalling(modelId)
    await onInstall(modelId)
    setInstalling(null)
  }

  async function handleConfirmedSwitch() {
    if (!confirmModel) return
    const target = confirmModel
    setConfirmModel(null)
    await onSwitch(target)
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Embedding Model</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium">Provider</label>
              <div className="flex rounded-md border overflow-hidden mt-1">
                <button
                  type="button"
                  className={`flex-1 text-xs py-2 px-3 transition-colors ${provider === "local" ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}
                  onClick={() => setProvider("local")}
                >
                  Local (ONNX)
                </button>
                <button
                  type="button"
                  className={`flex-1 text-xs py-2 px-3 transition-colors ${provider === "remote" ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}
                  onClick={() => setProvider("remote")}
                >
                  Remote (Ollama / API)
                </button>
              </div>
            </div>

            {provider === "remote" && (
              <div className="space-y-3 p-3 border rounded-md">
                <div>
                  <label className="text-sm font-medium">API Type</label>
                  <Select value={remoteApiType} onValueChange={setRemoteApiType}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ollama">Ollama</SelectItem>
                      <SelectItem value="openai">OpenAI-compatible</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-sm font-medium">API Base</label>
                  <Input
                    value={remoteApiBase}
                    onChange={(e) => setRemoteApiBase(e.target.value)}
                    placeholder={remoteApiType === "ollama" ? "http://192.168.x.x:11434" : "http://localhost:8080/v1"}
                    className="mt-1"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    {remoteApiType === "ollama"
                      ? "Ollama instance URL. The embedding model must be pulled on that server."
                      : "Any OpenAI-compatible embedding endpoint."}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium">Model</label>
                  <Input
                    value={remoteModel}
                    onChange={(e) => setRemoteModel(e.target.value)}
                    placeholder="nomic-embed-text"
                    className="mt-1"
                  />
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleTestRemote}>
                    Test Connection
                  </Button>
                  <Button size="sm" onClick={handleSaveProvider} disabled={saving || !remoteApiBase}>
                    {saving ? "Saving..." : "Save"}
                  </Button>
                </div>
                {testStatus && (
                  <pre className="text-xs bg-muted p-2 rounded whitespace-pre-wrap">{testStatus}</pre>
                )}
              </div>
            )}

            {provider === "local" && initialProvider === "remote" && (
              <div className="flex justify-end">
                <Button size="sm" onClick={handleSaveProvider} disabled={saving}>
                  Switch to Local
                </Button>
              </div>
            )}
          </div>
          {models.map((m) => {
            const isActive = m.model_id === activeModel
            return (
              <div
                key={m.model_id}
                className="flex items-center justify-between gap-4 p-3 rounded-md border"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{m.display_name}</span>
                    {isActive && <Badge>Active</Badge>}
                    {m.installed && !isActive && (
                      <Badge variant="secondary">Installed</Badge>
                    )}
                    {!m.installed && (
                      <Badge variant="outline">Not installed</Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {m.description} {m.dimensions}d, max {m.max_seq_length} tokens.
                    {m.local_path && (
                      <span className="inline-flex items-center gap-1 ml-1 text-muted-foreground" title={m.local_path}>
                        <FolderOpen className="h-3 w-3" /> Local
                      </span>
                    )}
                  </p>
                </div>
                <div className="flex gap-2 shrink-0">
                  {!m.installed && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleInstall(m.model_id)}
                      disabled={installing !== null || switching}
                    >
                      {installing === m.model_id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : m.local_path ? (
                        <FolderOpen className="h-4 w-4" />
                      ) : (
                        <Download className="h-4 w-4" />
                      )}
                      <span className="ml-1">
                        {installing === m.model_id
                          ? "Installing"
                          : m.local_path
                            ? "Copy"
                            : "Download"}
                      </span>
                    </Button>
                  )}
                  {m.installed && !isActive && (
                    <>
                      <Button
                        size="sm"
                        onClick={() => setConfirmModel(m.model_id)}
                        disabled={switching}
                      >
                        Use
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setConfirmDelete(m.model_id)}
                        disabled={switching}
                        title="Remove downloaded model"
                      >
                        <Trash2 className="h-4 w-4 text-muted-foreground" />
                      </Button>
                    </>
                  )}
                  {isActive && !switching && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setConfirmReindex(true)}
                    >
                      <RefreshCw className="h-4 w-4 mr-1" />
                      Re-index
                    </Button>
                  )}
                  {isActive && switching && (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={onCancel}
                    >
                      <Square className="h-3.5 w-3.5 mr-1" />
                      Stop
                    </Button>
                  )}
                </div>
              </div>
            )
          })}

          {status && (
            <div className="bg-muted p-3 rounded-md">
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {status}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmModel !== null}
        onOpenChange={(open) => { if (!open) setConfirmModel(null) }}
        title="Switch Embedding Model?"
        description={
          `Switching to "${confirmModel}" will clear all indexed data ` +
          `and reindex every document. This may take several minutes ` +
          `depending on your collection size.`
        }
        confirmLabel="Switch & Reindex"
        variant="destructive"
        onConfirm={handleConfirmedSwitch}
      />

      <ConfirmDialog
        open={confirmReindex}
        onOpenChange={setConfirmReindex}
        title="Force Re-index All Files?"
        description={
          `This will re-embed every document from scratch, even if ` +
          `the files haven't changed. This may take several minutes ` +
          `depending on your collection size.`
        }
        confirmLabel="Re-index All"
        variant="destructive"
        onConfirm={() => { setConfirmReindex(false); onReindex(true) }}
      />

      <ConfirmDialog
        open={confirmDelete !== null}
        onOpenChange={(open) => { if (!open) setConfirmDelete(null) }}
        title="Remove Embedding Model?"
        description={
          `This will delete the downloaded files for "${confirmDelete}". ` +
          `You can re-download it later from the Settings UI.`
        }
        confirmLabel="Remove"
        variant="destructive"
        onConfirm={() => { const id = confirmDelete; setConfirmDelete(null); if (id) onUninstall(id) }}
      />
    </>
  )
}
