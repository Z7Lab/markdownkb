import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { Copy, ScrollText, Trash2 } from "lucide-react"
import type { LogEntry } from "@/lib/types"

interface LoggingPanelProps {
  logLevel: string
  onSetLogLevel: (level: string) => Promise<void>
}

export function LoggingPanel({ logLevel, onSetLogLevel }: LoggingPanelProps) {
  const [entries, setEntries] = useState<LogEntry[]>([])
  const seqRef = useRef(0)
  const scrollRef = useRef<HTMLDivElement>(null)

  const fetchLogs = useCallback(async () => {
    try {
      const res = await api.get<{ entries: LogEntry[]; seq: number }>(
        `/api/settings/logs?since=${seqRef.current}`,
      )
      if (res.entries.length > 0) {
        setEntries((prev) => {
          const combined = [...prev, ...res.entries]
          return combined.length > 500 ? combined.slice(-500) : combined
        })
      }
      seqRef.current = res.seq
    } catch (err) {
      console.debug("Failed to fetch logs:", err)
    }
  }, [])

  // Poll every 2 seconds while panel is mounted
  useEffect(() => {
    fetchLogs()
    const interval = setInterval(fetchLogs, 2000)
    return () => clearInterval(interval)
  }, [fetchLogs])

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [entries])

  const handleClear = async () => {
    try {
      await api.del("/api/settings/logs")
      setEntries([])
      seqRef.current = 0
      toast.success("Logs cleared")
    } catch (err) {
      toast.error(`Failed to clear logs: ${(err as Error).message}`)
    }
  }

  const handleCopy = () => {
    const text = entries.map((e) => e.message).join("\n")
    navigator.clipboard.writeText(text)
    toast.success("Logs copied to clipboard")
  }

  const isVerbose = logLevel === "DEBUG"

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Logging</h2>
        <p className="text-sm text-muted-foreground">
          View application logs for debugging and troubleshooting
        </p>
      </div>

      <div className="flex items-center justify-between p-4 border rounded-lg">
        <div className="flex-1 space-y-1">
          <Label htmlFor="verbose-logging" className="text-base font-medium">
            Verbose Logging
          </Label>
          <p className="text-sm text-muted-foreground">
            Enable DEBUG level logging for detailed diagnostic output
          </p>
        </div>
        <Switch
          id="verbose-logging"
          checked={isVerbose}
          onCheckedChange={(checked) => onSetLogLevel(checked ? "DEBUG" : "INFO")}
        />
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <ScrollText className="h-4 w-4" />
                Log Output
              </CardTitle>
              <CardDescription>
                {entries.length} entries (last 500 kept)
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
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
    </div>
  )
}
