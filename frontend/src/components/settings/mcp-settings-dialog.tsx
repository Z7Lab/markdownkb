import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { api } from "@/lib/api"
import { toast } from "sonner"

type McpToolConfig = {
  [key: string]: unknown
}

interface McpSettingsDialogProps {
  toolName: string
  toolLabel: string
  config: McpToolConfig
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (config: McpToolConfig) => void
}

export function McpSettingsDialog({
  toolName,
  toolLabel,
  config: initialConfig,
  open,
  onOpenChange,
  onSave,
}: McpSettingsDialogProps) {
  const [config, setConfig] = useState<McpToolConfig>(initialConfig || {})
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.patch("/api/v1/settings/mcp", {
        tool_name: toolName,
        config,
      })
      onSave(config)
      toast.success(`${toolLabel} settings saved`)
      onOpenChange(false)
    } catch (err) {
      toast.error(`Failed to save settings: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  const updateField = (key: string, value: unknown) => {
    setConfig((prev) => ({ ...prev, [key]: value }))
  }

  // Render different input types based on the tool
  const renderToolSettings = () => {
    if (toolName === "tag_generator") {
      return (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="auto_apply">Auto-apply Tags</Label>
              <p className="text-xs text-muted-foreground">
                Apply tags automatically without preview
              </p>
            </div>
            <Switch
              id="auto_apply"
              checked={config.auto_apply as boolean || false}
              onCheckedChange={(checked) => updateField("auto_apply", checked)}
            />
          </div>
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="use_similar_docs">Use Similar Documents</Label>
              <p className="text-xs text-muted-foreground">
                Use tags from similar docs for context
              </p>
            </div>
            <Switch
              id="use_similar_docs"
              checked={config.use_similar_docs as boolean !== false}
              onCheckedChange={(checked) => updateField("use_similar_docs", checked)}
            />
          </div>
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="merge_with_existing">Merge with Existing Tags</Label>
              <p className="text-xs text-muted-foreground">
                Merge instead of replacing existing tags
              </p>
            </div>
            <Switch
              id="merge_with_existing"
              checked={config.merge_with_existing as boolean !== false}
              onCheckedChange={(checked) => updateField("merge_with_existing", checked)}
            />
          </div>
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="create_backup">Create Backup</Label>
              <p className="text-xs text-muted-foreground">
                Create backup before modifying files
              </p>
            </div>
            <Switch
              id="create_backup"
              checked={config.create_backup as boolean !== false}
              onCheckedChange={(checked) => updateField("create_backup", checked)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="max_tags">Maximum Tags</Label>
            <Input
              id="max_tags"
              type="number"
              value={config.max_tags as number || 7}
              onChange={(e) => { const v = parseInt(e.target.value, 10); if (!isNaN(v)) updateField("max_tags", v) }}
              min={1}
              max={20}
            />
            <p className="text-xs text-muted-foreground">
              Maximum number of tags to generate
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="content_preview_length">Content Preview Length</Label>
            <Input
              id="content_preview_length"
              type="number"
              value={config.content_preview_length as number || 1000}
              onChange={(e) => { const v = parseInt(e.target.value, 10); if (!isNaN(v)) updateField("content_preview_length", v) }}
              min={100}
              max={5000}
            />
            <p className="text-xs text-muted-foreground">
              Characters of content to analyze
            </p>
          </div>
        </div>
      )
    }

    return (
      <p className="text-sm text-muted-foreground">
        No configuration options available for this tool.
      </p>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{toolLabel} Settings</DialogTitle>
          <DialogDescription>
            Configure options for the {toolLabel} MCP tool.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">{renderToolSettings()}</div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
