import { Activity, AlertCircle, CheckCircle2 } from "lucide-react"
import { useLLMStatus } from "@/hooks/use-llm-status"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

export function LLMStatusIndicator() {
  const { status, lastChecked, availableModels, provider, checkStatus } = useLLMStatus()

  const statusConfig = {
    online: {
      icon: CheckCircle2,
      color: "text-green-500",
      bg: "bg-green-500/10",
      label: "Provider Online",
    },
    offline: {
      icon: AlertCircle,
      color: "text-red-500",
      bg: "bg-red-500/10",
      label: "Provider Offline",
    },
    checking: {
      icon: Activity,
      color: "text-yellow-500",
      bg: "bg-yellow-500/10",
      label: "Checking...",
    },
  }

  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={checkStatus}
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors hover:bg-accent",
            config.bg,
          )}
        >
          <Icon className={cn("h-3.5 w-3.5", config.color)} />
          <span className={cn("text-xs font-medium", config.color)}>
            {status === "checking" ? "..." : status.toUpperCase()}
          </span>
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <div className="space-y-1.5">
          <p className="font-medium">{config.label}</p>
          {provider && (
            <p className="text-muted-foreground">
              Provider: {provider}
            </p>
          )}
          {availableModels.length > 0 && (
            <div className="space-y-1">
              <p className="text-muted-foreground">Available models:</p>
              <ul className="text-xs space-y-0.5 list-disc list-inside">
                {availableModels.map((model) => (
                  <li key={model}>{model}</li>
                ))}
              </ul>
            </div>
          )}
          {lastChecked && (
            <p className="text-muted-foreground text-xs pt-1 border-t">
              Last checked: {lastChecked.toLocaleTimeString()}
            </p>
          )}
          <p className="text-muted-foreground text-xs pt-1 border-t">
            Click to recheck
          </p>
        </div>
      </TooltipContent>
    </Tooltip>
  )
}
