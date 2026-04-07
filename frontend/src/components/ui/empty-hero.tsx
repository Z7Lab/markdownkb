import type { LucideIcon } from "lucide-react"

/**
 * Empty-state hero for tabs that haven't been used yet.
 * Shows a large icon + label above the input area.
 * Used by Search, Chat, and Planner tabs for a consistent look.
 */
export function EmptyHero({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <div className="flex flex-col items-center gap-3 select-none">
      <Icon className="h-12 w-12 text-primary/20" strokeWidth={1.5} />
      <span className="text-2xl font-light tracking-wide text-primary/40">{label}</span>
    </div>
  )
}
