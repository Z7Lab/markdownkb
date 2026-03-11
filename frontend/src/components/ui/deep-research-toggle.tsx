import { Switch } from "@/components/ui/switch"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Microscope } from "lucide-react"

/**
 * Reusable deep research toggle — can be placed in any tab (search, chat, graph, etc.)
 * Renders nothing if the deep_research feature flag is disabled.
 */
export function DeepResearchToggle({
  enabled,
  onToggle,
  featureEnabled,
  disabled = false,
}: {
  enabled: boolean
  onToggle: (value: boolean) => void
  featureEnabled: boolean
  disabled?: boolean
}) {
  if (!featureEnabled) return null

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center gap-1.5">
          <Microscope className={`h-3.5 w-3.5 ${enabled ? "text-primary" : "text-muted-foreground"}`} />
          <span className={`text-xs select-none ${enabled ? "text-primary font-medium" : "text-muted-foreground"}`}>
            Deep
          </span>
          <Switch
            size="sm"
            checked={enabled}
            onCheckedChange={onToggle}
            disabled={disabled}
          />
        </div>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p>Deep Research uses MCTS to explore multiple angles before synthesizing a comprehensive summary. Slower but more thorough.</p>
      </TooltipContent>
    </Tooltip>
  )
}
