import { useCallback, useEffect, useState } from "react"
import { Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { LogViewer } from "./log-viewer"

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const
type LogLevel = (typeof LOG_LEVELS)[number]

interface LogOverridesResponse {
  user: Record<string, string>
  plugin_defaults: Record<string, Record<string, string>>
}

interface LoggingPanelProps {
  logLevel: string
  onSetLogLevel: (level: string) => Promise<void>
}

export function LoggingPanel({ logLevel, onSetLogLevel }: LoggingPanelProps) {
  const [overrides, setOverrides] = useState<LogOverridesResponse>({
    user: {},
    plugin_defaults: {},
  })
  const [newLogger, setNewLogger] = useState("")
  const [newLevel, setNewLevel] = useState<LogLevel>("WARNING")
  const [saving, setSaving] = useState(false)

  const fetchOverrides = useCallback(async () => {
    const data = await api.get<LogOverridesResponse>("/api/v1/settings/log-overrides")
    setOverrides(data)
  }, [])

  useEffect(() => {
    fetchOverrides()
  }, [fetchOverrides])

  const saveOverrides = useCallback(async (updated: Record<string, string>) => {
    setSaving(true)
    try {
      await api.put("/api/v1/settings/log-overrides", { overrides: updated })
      setOverrides((prev) => ({ ...prev, user: updated }))
    } catch {
      toast.error("Failed to save logger overrides")
    } finally {
      setSaving(false)
    }
  }, [])

  const handleRemove = useCallback(
    (name: string) => {
      const updated = { ...overrides.user }
      delete updated[name]
      saveOverrides(updated)
    },
    [overrides.user, saveOverrides],
  )

  const handleLevelChange = useCallback(
    (name: string, level: string) => {
      saveOverrides({ ...overrides.user, [name]: level })
    },
    [overrides.user, saveOverrides],
  )

  const handleAdd = useCallback(() => {
    const name = newLogger.trim()
    if (!name) return
    saveOverrides({ ...overrides.user, [name]: newLevel })
    setNewLogger("")
    setNewLevel("WARNING")
  }, [newLogger, newLevel, overrides.user, saveOverrides])

  const pluginEntries = Object.entries(overrides.plugin_defaults)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Logging</h2>
        <p className="text-sm text-muted-foreground">
          View application logs for debugging and troubleshooting
        </p>
      </div>

      <LogViewer
        logsUrl="/api/v1/settings/logs"
        title="Log Output"
        description="Application server logs"
        logLevel={logLevel}
        onLogLevelChange={onSetLogLevel}
      />

      <div className="space-y-4">
        <div>
          <h3 className="text-base font-semibold mb-1">Logger Overrides</h3>
          <p className="text-sm text-muted-foreground">
            Fine-tune verbosity for specific libraries. Plugin defaults apply automatically when a plugin is enabled; custom overrides take precedence.
          </p>
        </div>

        {pluginEntries.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Plugin Defaults
            </p>
            <div className="rounded-md border divide-y">
              {pluginEntries.map(([pluginName, loggers]) =>
                Object.entries(loggers).map(([loggerName, level]) => (
                  <div
                    key={`${pluginName}:${loggerName}`}
                    className="flex items-center justify-between px-3 py-2 text-sm"
                  >
                    <span className="font-mono text-xs">{loggerName}</span>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-xs font-mono">
                        {level}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        from {pluginName}
                      </span>
                    </div>
                  </div>
                )),
              )}
            </div>
          </div>
        )}

        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Custom Overrides
          </p>
          <div className="rounded-md border divide-y">
            {Object.entries(overrides.user).map(([name, level]) => (
              <div key={name} className="flex items-center gap-2 px-3 py-2">
                <span className="font-mono text-xs flex-1 truncate">{name}</span>
                <Select
                  value={level}
                  onValueChange={(v) => handleLevelChange(name, v)}
                  disabled={saving}
                >
                  <SelectTrigger className="h-7 w-28 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {LOG_LEVELS.map((l) => (
                      <SelectItem key={l} value={l} className="text-xs font-mono">
                        {l}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0"
                  onClick={() => handleRemove(name)}
                  disabled={saving}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
            <div className="flex items-center gap-2 px-3 py-2">
              <Input
                value={newLogger}
                onChange={(e) => setNewLogger(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAdd()}
                placeholder="logger.name"
                className="h-7 text-xs font-mono flex-1"
              />
              <Select
                value={newLevel}
                onValueChange={(v) => setNewLevel(v as LogLevel)}
              >
                <SelectTrigger className="h-7 w-28 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LOG_LEVELS.map((l) => (
                    <SelectItem key={l} value={l} className="text-xs font-mono">
                      {l}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0"
                onClick={handleAdd}
                disabled={saving || !newLogger.trim()}
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
