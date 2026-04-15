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

const EMBEDDING_PROVIDERS = [
  {
    name: "local",
    label: "Local (ONNX)",
    desc: "Runs on CPU, no external service needed. Ships with the app — works out of the box.",
  },
  {
    name: "ollama",
    label: "Ollama",
    desc: "Use an embedding model from your Ollama instance. The model must be pulled on the server first.",
  },
  {
    name: "openai",
    label: "OpenAI-compatible API",
    desc: "Any embedding API with an OpenAI-compatible endpoint — OpenAI, Venice, Together, or a self-hosted server.",
  },
]

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

  // Map initial provider to our simplified list
  const mapProvider = (p: string): string => {
    if (p === "remote") {
      return initialRemoteConfig?.api_type === "ollama" ? "ollama" : "openai"
    }
    return "local"
  }

  const [provider, setProvider] = useState(mapProvider(initialProvider))
  const [remoteModel, setRemoteModel] = useState(initialRemoteConfig?.model || "nomic-embed-text")
  const [remoteApiBase, setRemoteApiBase] = useState(initialRemoteConfig?.api_base || "")
  const [remoteApiKey, setRemoteApiKey] = useState("")
  const [testStatus, setTestStatus] = useState("")
  const [saving, setSaving] = useState(false)

  const isRemote = provider !== "local"
  const apiType = provider === "ollama" ? "ollama" : "openai"

  const handleSaveProvider = useCallback(async () => {
    setSaving(true)
    try {
      await api.put("/api/v1/settings/embedding-provider", {
        provider: isRemote ? "remote" : "local",
        remote_model: remoteModel,
        api_base: remoteApiBase,
        api_type: apiType,
        api_key: remoteApiKey,
      })
      setTestStatus("Saved")
    } catch (err) {
      setTestStatus(`Error: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }, [isRemote, remoteModel, remoteApiBase, apiType, remoteApiKey])

  const handleTestRemote = useCallback(async () => {
    setTestStatus("Testing...")
    try {
      const res = await api.post<{ ok: boolean; message: string; dimensions?: number }>("/api/v1/settings/embedding-models/test-remote", {
        model: remoteModel,
        api_base: remoteApiBase,
        api_type: apiType,
        api_key: remoteApiKey,
      })
      setTestStatus(res.message)
    } catch (err) {
      setTestStatus(`Error: ${(err as Error).message}`)
    }
  }, [remoteModel, remoteApiBase, apiType, remoteApiKey])

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

  const providerInfo = EMBEDDING_PROVIDERS.find((p) => p.name === provider)

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Embedding Model</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Provider selection */}
          <div>
            <label className="text-sm font-medium">Provider</label>
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EMBEDDING_PROVIDERS.map((p) => (
                  <SelectItem key={p.name} value={p.name}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {providerInfo && (
              <p className="text-xs text-muted-foreground mt-1.5">{providerInfo.desc}</p>
            )}
          </div>

          {/* Remote config */}
          {isRemote && (
            <div className="space-y-3 p-3 border rounded-md">
              <div>
                <label className="text-sm font-medium">API Base</label>
                <Input
                  value={remoteApiBase}
                  onChange={(e) => setRemoteApiBase(e.target.value)}
                  placeholder={provider === "ollama" ? "http://localhost:11434" : "https://api.openai.com/v1"}
                  className="mt-1"
                />
                {provider === "ollama" && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Ollama instance URL. The embedding model must be pulled first
                    (e.g. <code className="text-[10px]">ollama pull nomic-embed-text</code>).
                    Docker users: use <code className="text-[10px]">http://host.docker.internal:11434</code>.
                  </p>
                )}
                {provider === "openai" && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Works with OpenAI, Venice (<code className="text-[10px]">https://api.venice.ai/api/v1</code>),
                    Together, or any server exposing <code className="text-[10px]">/v1/embeddings</code>.
                  </p>
                )}
              </div>
              <div>
                <label className="text-sm font-medium">Model</label>
                <Input
                  value={remoteModel}
                  onChange={(e) => setRemoteModel(e.target.value)}
                  placeholder={provider === "ollama" ? "nomic-embed-text" : "text-embedding-3-small"}
                  className="mt-1"
                />
              </div>
              {provider === "openai" && (
                <div>
                  <label className="text-sm font-medium">API Key</label>
                  <Input
                    type="password"
                    value={remoteApiKey}
                    onChange={(e) => setRemoteApiKey(e.target.value)}
                    placeholder="Required for authenticated providers"
                    className="mt-1"
                  />
                </div>
              )}
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleTestRemote} disabled={!remoteApiBase}>
                  Test
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

          {/* Switch back to local */}
          {provider === "local" && initialProvider === "remote" && (
            <div className="flex justify-end">
              <Button size="sm" onClick={handleSaveProvider} disabled={saving}>
                Switch to Local
              </Button>
            </div>
          )}

          {/* Local ONNX model list — only show when local is selected */}
          {provider === "local" && (
            <div className="space-y-3">
              <div className="rounded-md border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20 p-3 space-y-2">
                <p className="text-xs font-medium">What are embedding models?</p>
                <p className="text-xs text-muted-foreground">
                  Embedding models convert your documents into numerical vectors for semantic search.
                  They're separate from the chat model — embeddings run locally via ONNX (a portable model format that works on any CPU, no GPU needed).
                </p>
                <p className="text-xs text-muted-foreground">
                  Models are downloaded from{" "}
                  <a href="https://huggingface.co" target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline">
                    HuggingFace
                  </a>{" "}
                  on first install. Switching models clears all embeddings and triggers a full re-index.
                </p>
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
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {m.local_path ? (
                          <span className="inline-flex items-center gap-1" title={m.local_path}>
                            <FolderOpen className="h-3 w-3" /> Local install
                          </span>
                        ) : m.huggingface_repo ? (
                          <a
                            href={`https://huggingface.co/${m.huggingface_repo}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1"
                          >
                            {m.huggingface_repo}
                          </a>
                        ) : null}
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
            </div>
          )}

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
