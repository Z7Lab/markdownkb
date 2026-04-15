import { LogViewer } from "./log-viewer"

interface LoggingPanelProps {
  logLevel: string
  onSetLogLevel: (level: string) => Promise<void>
}

export function LoggingPanel({ logLevel, onSetLogLevel }: LoggingPanelProps) {
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
    </div>
  )
}
