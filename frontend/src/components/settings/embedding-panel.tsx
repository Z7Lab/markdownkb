import { useState } from "react"
import { Download, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import type { EmbeddingModel } from "@/lib/types"

export function EmbeddingPanel({
  models,
  activeModel,
  status,
  onInstall,
  onSwitch,
}: {
  models: EmbeddingModel[]
  activeModel: string
  status: string
  onInstall: (modelId: string) => Promise<void>
  onSwitch: (modelId: string) => Promise<void>
}) {
  const [confirmModel, setConfirmModel] = useState<string | null>(null)
  const [installing, setInstalling] = useState<string | null>(null)
  const [switching, setSwitching] = useState(false)

  async function handleInstall(modelId: string) {
    setInstalling(modelId)
    await onInstall(modelId)
    setInstalling(null)
  }

  async function handleConfirmedSwitch() {
    if (!confirmModel) return
    const target = confirmModel
    setConfirmModel(null)
    setSwitching(true)
    await onSwitch(target)
    setSwitching(false)
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Embedding Model</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
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
                      ) : (
                        <Download className="h-4 w-4" />
                      )}
                      <span className="ml-1">
                        {installing === m.model_id ? "Installing" : "Install"}
                      </span>
                    </Button>
                  )}
                  {m.installed && !isActive && (
                    <Button
                      size="sm"
                      onClick={() => setConfirmModel(m.model_id)}
                      disabled={switching}
                    >
                      {switching ? (
                        <Loader2 className="h-4 w-4 animate-spin mr-1" />
                      ) : null}
                      Use
                    </Button>
                  )}
                </div>
              </div>
            )
          })}

          {status && (
            <p className="text-sm text-muted-foreground bg-muted p-3 rounded-md whitespace-pre-wrap">
              {status}
            </p>
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
    </>
  )
}
