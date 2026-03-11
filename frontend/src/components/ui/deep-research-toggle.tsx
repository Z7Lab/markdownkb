import { Switch } from "@/components/ui/switch"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Microscope } from "lucide-react"

const ITERATION_OPTIONS = [1, 2, 3, 5, 8, 10]

/**
 * Reusable deep research toggle — can be placed in any tab (search, chat, graph, etc.)
 * Renders nothing if the deep_research feature flag is disabled.
 */
export function DeepResearchToggle({
  enabled,
  onToggle,
  featureEnabled,
  disabled = false,
  iterations = 3,
  onIterationsChange,
}: {
  enabled: boolean
  onToggle: (value: boolean) => void
  featureEnabled: boolean
  disabled?: boolean
  iterations?: number
  onIterationsChange?: (value: number) => void
}) {
  if (!featureEnabled) return null

  return (
    <div className="flex items-center gap-1.5">
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
      {enabled && onIterationsChange && (
        <Tooltip>
          <TooltipTrigger asChild>
            <div>
              <Select
                value={String(iterations)}
                onValueChange={(v) => onIterationsChange(Number(v))}
                disabled={disabled}
              >
                <SelectTrigger className="h-6 w-14 text-xs px-1.5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ITERATION_OPTIONS.map((n) => (
                    <SelectItem key={n} value={String(n)} className="text-xs">
                      {n}x
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            <p>Research depth — number of MCTS iterations. Higher = more thorough but slower.</p>
          </TooltipContent>
        </Tooltip>
      )}
    </div>
  )
}
