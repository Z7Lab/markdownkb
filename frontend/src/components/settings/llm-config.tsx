import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { AppSettings } from "@/lib/types"

export function LlmConfig({
  settings,
  status,
  onSave,
  onTest,
  onRefreshModels,
}: {
  settings: AppSettings
  status: string
  onSave: (name: string, model: string, apiBase: string) => Promise<void>
  onTest: (name: string, model: string, apiBase: string) => Promise<void>
  onRefreshModels: (name: string, apiBase: string) => Promise<{ models: string[]; status: string }>
}) {
  const [provider, setProvider] = useState(settings.active_provider)
  const [model, setModel] = useState(settings.active_model)
  const [apiBase, setApiBase] = useState(settings.active_api_base)
  const [models, setModels] = useState<string[]>([])

  function onProviderChange(name: string) {
    setProvider(name)
    const p = settings.providers.find((x) => x.name === name)
    if (p) {
      setModel(p.model)
      setApiBase(p.api_base)
    }
  }

  async function handleRefresh() {
    const res = await onRefreshModels(provider, apiBase)
    if (res.models.length > 0) {
      setModels(res.models)
      setModel(res.models[0])
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>LLM Configuration</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="text-sm font-medium">Provider</label>
          <Select value={provider} onValueChange={onProviderChange}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {settings.providers.map((p) => (
                <SelectItem key={p.name} value={p.name}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <label className="text-sm font-medium">API Base</label>
          <Input
            value={apiBase}
            onChange={(e) => setApiBase(e.target.value)}
            placeholder="Leave empty for default"
          />
        </div>

        <div>
          <label className="text-sm font-medium">Model</label>
          <div className="flex gap-2">
            {models.length > 0 ? (
              <Select value={model} onValueChange={setModel}>
                <SelectTrigger className="flex-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {models.map((m) => (
                    <SelectItem key={m} value={m}>{m}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="flex-1"
              />
            )}
            <Button variant="outline" size="sm" onClick={handleRefresh}>
              Refresh
            </Button>
          </div>
        </div>

        <div className="flex gap-2">
          <Button onClick={() => onSave(provider, model, apiBase)}>
            Save
          </Button>
          <Button variant="secondary" onClick={() => onTest(provider, model, apiBase)}>
            Test Connection
          </Button>
        </div>

        {status && (
          <pre className="text-sm bg-muted p-3 rounded-md whitespace-pre-wrap">
            {status}
          </pre>
        )}
      </CardContent>
    </Card>
  )
}
