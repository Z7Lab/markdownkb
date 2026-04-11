import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { copyToClipboard } from "@/lib/utils"
import { Copy, ScrollText, Trash2 } from "lucide-react"
import type { LogEntry } from "@/lib/types"

interface LogViewerProps {
  /** GET and DELETE endpoint for the log ring buffer. */
  logsUrl: string
  title?: string
  description?: string
  /** Controlled log level — shows a Verbose toggle when provided alongside onLogLevelChange. */
  logLevel?: string
  onLogLevelChange?: (level: string) => Promise<void>
}

export function LogViewer({
  logsUrl,
  title = "Log Output",
  description,
  logLevel,
  onLogLevelChange,
}: LogViewerProps) {
  const [entries, setEntries] = useState<LogEntry[]>([])
  const seqRef = useRef(0)
  const scrollRef = useRef<HTMLDivElement>(null)

  const fetchLogs = useCallback(async () => {
    try {
      const res = await api.get<{ entries: LogEntry[]; seq: number }>(
        `${logsUrl}?since=${seqRef.current}`,
      )
      if (res.entries.length > 0) {
        setEntries((prev) => {
          const combined = [...prev, ...res.entries]
          return combined.length > 500 ? combined.slice(-500) : combined
        })
      }
      seqRef.current = res.seq
    } catch {
      // Silently drop poll errors (MCP server may be temporarily unreachable)
    }
  }, [logsUrl])

  // Reset and restart polling whenever the URL changes
  useEffect(() => {
    setEntries([])
    seqRef.current = 0
    fetchLogs()
    const interval = setInterval(fetchLogs, 2000)
    return () => clearInterval(interval)
  }, [fetchLogs])

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [entries])

  const handleClear = async () => {
    try {
      await api.del(logsUrl)
      setEntries([])
      seqRef.current = 0
      toast.success("Logs cleared")
    } catch (err) {
      toast.error(`Failed to clear logs: ${(err as Error).message}`)
    }
  }

  const handleCopy = async () => {
    const text = entries.map((e) => e.message).join("\n")
    const ok = await copyToClipboard(text)
    if (ok) {
      toast.success("Logs copied to clipboard")
    } else {
      toast.error("Failed to copy logs")
    }
  }

  const showVerboseToggle = !!onLogLevelChange

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <ScrollText className="h-4 w-4" />
              {title}
            </CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
            <CardDescription>{entries.length} entries (last 500 kept)</CardDescription>
          </div>
          <div className="flex items-center gap-3">
            {showVerboseToggle && (
              <div className="flex items-center gap-2">
                <Switch
                  id={`verbose-${logsUrl}`}
                  checked={logLevel === "DEBUG"}
                  onCheckedChange={(checked) =>
                    onLogLevelChange(checked ? "DEBUG" : "INFO")
                  }
                />
                <Label
                  htmlFor={`verbose-${logsUrl}`}
                  className="text-xs text-muted-foreground cursor-pointer"
                >
                  Verbose
                </Label>
              </div>
            )}
            <Button
              variant="outline"
              size="icon"
              onClick={handleCopy}
              disabled={entries.length === 0}
              title="Copy logs to clipboard"
            >
              <Copy className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={handleClear}
              disabled={entries.length === 0}
              title="Clear logs"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div
          ref={scrollRef}
          className="h-80 overflow-y-auto rounded-md bg-muted/50 p-3 font-mono text-xs leading-relaxed"
        >
          {entries.length === 0 ? (
            <p className="text-muted-foreground italic">No log entries yet</p>
          ) : (
            entries.map((entry, i) => (
              <div
                key={`${entry.timestamp}-${i}`}
                className={
                  entry.level === "ERROR" || entry.level === "CRITICAL"
                    ? "text-destructive"
                    : entry.level === "WARNING"
                      ? "text-yellow-600 dark:text-yellow-400"
                      : entry.level === "DEBUG"
                        ? "text-muted-foreground"
                        : ""
                }
              >
                {entry.message}
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  )
}
