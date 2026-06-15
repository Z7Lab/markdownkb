import { Info } from "lucide-react"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

/**
 * Small inline help affordance — an info icon that reveals explanatory text
 * on hover/focus. Wraps the app's standard Tooltip + Info-icon idiom so the
 * boilerplate lives in one place. Relies on the global <TooltipProvider> in
 * App.tsx.
 */
export function HelpTip({
  children,
  className,
  side = "top",
}: {
  children: React.ReactNode
  className?: string
  side?: "top" | "right" | "bottom" | "left"
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Info
          className={cn("h-3.5 w-3.5 text-muted-foreground cursor-help shrink-0", className)}
          aria-label="Help"
        />
      </TooltipTrigger>
      <TooltipContent side={side} className="max-w-xs">
        {children}
      </TooltipContent>
    </Tooltip>
  )
}
