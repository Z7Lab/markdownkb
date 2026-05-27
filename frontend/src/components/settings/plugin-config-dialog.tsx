import { useEffect, useState } from "react"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { api } from "@/lib/api"
import { toast } from "sonner"
import type { PluginInfo } from "./plugin-types"

export function PluginConfigDialog({
  plugin,
  open,
  onOpenChange,
  onSaved,
}: {
  plugin: PluginInfo
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}) {
  const [config, setConfig] = useState<Record<string, unknown>>(plugin.config || {})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setConfig(plugin.config || {})
  }, [plugin.config])

  const schema = plugin.config_schema || {}
  const fields = Object.entries(schema).filter(([, v]) => v && typeof v === "object" && v.type)

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put(`/api/v1/settings/plugins/${plugin.name}`, config)
      toast.success(`${plugin.display_name} config saved`)
      onSaved()
      onOpenChange(false)
    } catch (err) {
      toast.error(`Failed to save: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  const updateField = (key: string, value: unknown) => {
    setConfig((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{plugin.display_name} Settings</DialogTitle>
          {plugin.description && (
            <DialogDescription>{plugin.description}</DialogDescription>
          )}
        </DialogHeader>

        <div className="py-4 space-y-4">
          {fields.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No configuration options available.
            </p>
          ) : (
            fields.map(([key, field]) => {
              const value = config[key] ?? field.default
              if (field.type === "boolean") {
                return (
                  <div key={key} className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor={key}>{field.label || key}</Label>
                      {field.description && (
                        <p className="text-xs text-muted-foreground">{field.description}</p>
                      )}
                    </div>
                    <Switch
                      id={key}
                      checked={value as boolean}
                      onCheckedChange={(checked) => updateField(key, checked)}
                    />
                  </div>
                )
              }
              if (field.type === "integer" || field.type === "number") {
                return (
                  <div key={key} className="space-y-2">
                    <Label htmlFor={key}>{field.label || key}</Label>
                    <Input
                      id={key}
                      type="number"
                      value={value as number}
                      min={field.min}
                      max={field.max}
                      onChange={(e) => {
                        const n = parseInt(e.target.value, 10)
                        if (!isNaN(n)) updateField(key, n)
                      }}
                    />
                    {field.description && (
                      <p className="text-xs text-muted-foreground">{field.description}</p>
                    )}
                  </div>
                )
              }
              // Default: string
              return (
                <div key={key} className="space-y-2">
                  <Label htmlFor={key}>{field.label || key}</Label>
                  <Input
                    id={key}
                    value={value as string}
                    onChange={(e) => updateField(key, e.target.value)}
                  />
                  {field.description && (
                    <p className="text-xs text-muted-foreground">{field.description}</p>
                  )}
                </div>
              )
            })
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
