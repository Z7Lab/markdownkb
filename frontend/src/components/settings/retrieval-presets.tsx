import { useState, useEffect, useCallback } from "react"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { BookmarkPlus, Upload, Trash2, Info } from "lucide-react"
import { toast } from "sonner"

interface Preset {
  id: string
  name: string
  settings: {
    top_k: number
    score_threshold: number
    hybrid_search: boolean
    bm25_weight: number
  }
  created_at: string
  updated_at: string
}

interface RetrievalPresetsProps {
  /** Called after a preset is loaded so the parent form updates its values */
  onLoad: (settings: Preset["settings"]) => void
  /** Returns the current form values for snapshotting */
  getCurrentSettings: () => Preset["settings"]
}

export function RetrievalPresets({ onLoad, getCurrentSettings }: RetrievalPresetsProps) {
  const [presets, setPresets] = useState<Preset[]>([])
  const [newName, setNewName] = useState("")
  const [showSaveInput, setShowSaveInput] = useState(false)
  const [loading, setLoading] = useState(false)

  const fetchPresets = useCallback(async () => {
    try {
      const data = await api.get<{ presets: Preset[] }>("/api/settings/presets")
      setPresets(data.presets)
    } catch (err) {
      // Presets are optional — don't block the settings page, but log so
      // developers can see if the presets endpoint is broken.
      console.error("Failed to fetch retrieval presets:", err)
    }
  }, [])

  useEffect(() => { fetchPresets() }, [fetchPresets])

  async function handleLoad(presetId: string) {
    setLoading(true)
    try {
      const data = await api.post<{ status: string; name: string; settings: Preset["settings"] }>(
        `/api/settings/presets/${presetId}/load`,
      )
      onLoad(data.settings)
      toast.success(`Loaded preset "${data.name}"`)
    } catch (err) {
      toast.error(`Failed to load preset: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    const name = newName.trim()
    if (!name) return
    try {
      const settings = getCurrentSettings()
      await api.post("/api/settings/presets", { name, settings })
      toast.success(`Saved preset "${name}"`)
      setNewName("")
      setShowSaveInput(false)
      fetchPresets()
    } catch (err) {
      toast.error(`Failed to save: ${(err as Error).message}`)
    }
  }

  async function handleDelete(presetId: string) {
    const preset = presets.find(p => p.id === presetId)
    if (!preset) return
    try {
      await api.del(`/api/settings/presets/${presetId}`)
      toast.success(`Deleted preset "${preset.name}"`)
      fetchPresets()
    } catch (err) {
      toast.error(`Failed to delete: ${(err as Error).message}`)
    }
  }

  function formatPresetLabel(p: Preset) {
    const parts: string[] = []
    parts.push(`k=${p.settings.top_k}`)
    parts.push(`thresh=${(p.settings.score_threshold * 100).toFixed(0)}%`)
    if (p.settings.hybrid_search) {
      parts.push(`bm25=${p.settings.bm25_weight.toFixed(2)}`)
    } else {
      parts.push("vector-only")
    }
    return parts.join(", ")
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-medium">Presets</h4>
        <Tooltip>
          <TooltipTrigger asChild>
            <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            <p>Save and load retrieval setting configurations. Useful for switching between different tuning profiles.</p>
          </TooltipContent>
        </Tooltip>
      </div>

      <div className="flex items-center gap-2">
        {presets.length > 0 ? (
          <div className="flex items-center gap-1.5 flex-1 min-w-0">
            <Select onValueChange={handleLoad} disabled={loading}>
              <SelectTrigger className="flex-1 min-w-0 h-8 text-xs">
                <SelectValue placeholder="Load a preset..." />
              </SelectTrigger>
              <SelectContent>
                {presets.map(p => (
                  <SelectItem key={p.id} value={p.id} className="text-xs">
                    <span className="font-medium">{p.name}</span>
                    <span className="text-muted-foreground ml-2">({formatPresetLabel(p)})</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {presets.length > 0 && (
              <Select onValueChange={handleDelete}>
                <SelectTrigger className="w-8 h-8 p-0 flex items-center justify-center shrink-0">
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                </SelectTrigger>
                <SelectContent>
                  {presets.map(p => (
                    <SelectItem key={p.id} value={p.id} className="text-xs text-destructive">
                      Delete "{p.name}"
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground flex-1">No presets saved yet</p>
        )}

        {!showSaveInput && (
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs shrink-0"
            onClick={() => setShowSaveInput(true)}
          >
            <BookmarkPlus className="h-3.5 w-3.5 mr-1" />
            Save Current
          </Button>
        )}
      </div>

      {showSaveInput && (
        <div className="flex items-center gap-2">
          <Input
            value={newName}
            onChange={e => setNewName(e.target.value)}
            placeholder="Preset name..."
            className="h-8 text-xs flex-1"
            onKeyDown={e => {
              if (e.key === "Enter") handleSave()
              if (e.key === "Escape") { setShowSaveInput(false); setNewName("") }
            }}
            autoFocus
          />
          <Button size="sm" className="h-8 text-xs" onClick={handleSave} disabled={!newName.trim()}>
            <Upload className="h-3.5 w-3.5 mr-1" />
            Save
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 text-xs"
            onClick={() => { setShowSaveInput(false); setNewName("") }}
          >
            Cancel
          </Button>
        </div>
      )}
    </div>
  )
}
