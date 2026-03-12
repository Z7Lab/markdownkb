import { useEffect, useState } from "react"
import { useSettings } from "@/hooks/use-settings"
import type { ModelEntry } from "@/lib/types"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export function ModelPicker() {
  const { settings, refreshModels, saveProvider } = useSettings()
  const [models, setModels] = useState<ModelEntry[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!settings) return
    let cancelled = false
    // Wrap setLoading in Promise.resolve().then() to avoid set-state-in-effect warning
    Promise.resolve().then(() => {
      if (!cancelled) setLoading(true)
    })
    refreshModels(settings.active_provider, settings.active_api_base)
      .then((res) => {
        if (!cancelled && res.models.length > 0) setModels(res.models)
      })
      .catch(() => { /* model list is best-effort; current model still works */ })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [settings?.active_provider, settings?.active_api_base, settings, refreshModels])

  if (!settings) return null

  const activeModel = settings.active_model
  const options = [...models]
  if (activeModel && !models.some((m) => m.id === activeModel)) {
    options.unshift({ id: activeModel, label: activeModel })
  }

  return (
    <Select
      value={activeModel}
      onValueChange={(m) =>
        saveProvider(settings.active_provider, m, settings.active_api_base)
      }
      disabled={loading}
    >
      <SelectTrigger className="w-full text-xs h-8">
        <SelectValue
          placeholder={loading ? "Loading..." : "Select model"}
        />
      </SelectTrigger>
      <SelectContent>
        {options.map((m) => (
          <SelectItem key={m.id} value={m.id} className="text-xs">
            {m.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
