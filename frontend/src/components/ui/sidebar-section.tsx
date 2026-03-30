import { useState, type ReactNode } from "react"
import { Badge } from "@/components/ui/badge"
import { ChevronDown, ChevronRight, type LucideIcon } from "lucide-react"

/**
 * Collapsible sidebar section with icon, label, selection summary, and count badge.
 * Used by ScopeTagFilter, BucketSelector, and any plugin that adds sidebar filters.
 *
 * Starts collapsed by default. When collapsed with active selections,
 * shows a compact summary so the user knows something is checked.
 */
export function SidebarSection({
  icon: Icon,
  label,
  count,
  summary,
  defaultOpen = false,
  children,
}: {
  icon: LucideIcon
  label: string
  /** Number of active selections (shown as badge when > 0) */
  count?: number
  /** Short text shown next to the badge when collapsed (e.g. selected item names) */
  summary?: string
  defaultOpen?: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  const hasSelection = (count ?? 0) > 0

  return (
    <div className="space-y-1 px-1">
      <button
        className="flex items-center gap-2 w-full text-left min-w-0"
        onClick={() => setOpen(!open)}
      >
        {open ? (
          <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
        )}
        <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        {hasSelection && !open && summary && (
          <span className="text-[10px] text-muted-foreground/70 truncate min-w-0 flex-1">
            {summary}
          </span>
        )}
        {hasSelection && (
          <Badge variant="secondary" className="text-[10px] h-4 px-1 ml-auto shrink-0">
            {count}
          </Badge>
        )}
      </button>

      {open && children}
    </div>
  )
}
