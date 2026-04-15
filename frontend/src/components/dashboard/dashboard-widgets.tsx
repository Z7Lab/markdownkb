import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/**
 * Generic widget renderers for dashboard activity sections.
 * Each widget_type has a corresponding renderer component.
 */

// ============================================================================
// recent_activity: List of items with label + relative timestamp
// ============================================================================

export interface RecentActivityItem {
  id: string
  label: string
  timestamp: string | null  // ISO timestamp or relative string
  onClick?: () => void
  badge?: ReactNode
}

interface RecentActivityWidgetProps {
  items: RecentActivityItem[]
  label: string
  emptyMessage: string
}

export function RecentActivityWidget({
  items,
  label,
  emptyMessage,
}: RecentActivityWidgetProps) {
  if (items.length === 0) {
    return (
      <div className="space-y-3 text-sm">
        <h3 className="font-semibold text-muted-foreground">{label}</h3>
        <p className="text-xs text-muted-foreground">{emptyMessage}</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <h3 className="font-semibold text-sm">{label}</h3>
      <div className="space-y-2">
        {items.map((item) => (
          <div
            key={item.id}
            onClick={item.onClick}
            className={cn(
              "flex items-start justify-between gap-2 p-3 rounded-md border bg-card text-sm",
              item.onClick && "cursor-pointer hover:bg-accent transition-colors",
            )}
          >
            <div className="min-w-0 flex-1">
              <p className="font-medium text-sm truncate">{item.label}</p>
              {item.timestamp && (
                <p className="text-xs text-muted-foreground">{item.timestamp}</p>
              )}
            </div>
            {item.badge && <div className="shrink-0">{item.badge}</div>}
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================================================
// count: Single number with label and optional trend
// ============================================================================

interface CountWidgetProps {
  value: number | string
  label: string
  trend?: "up" | "down" | "stable"
  trendPercent?: number
}

export function CountWidget({
  value,
  label,
  trend,
  trendPercent,
}: CountWidgetProps) {
  return (
    <div className="p-4 rounded-lg border bg-card space-y-2">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        {label}
      </p>
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-bold">{value}</span>
        {trend && trendPercent !== undefined && (
          <div
            className={cn(
              "text-xs font-medium",
              trend === "up" && "text-green-600",
              trend === "down" && "text-red-600",
              trend === "stable" && "text-gray-600",
            )}
          >
            {trend === "up" && "↑"} {trend === "down" && "↓"}{" "}
            {Math.abs(trendPercent)}%
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// status: Status badge with optional action button
// ============================================================================

interface StatusWidgetProps {
  status: "ok" | "warning" | "error"
  message: string
  actionLabel?: string
  onAction?: () => void
  details?: ReactNode
}

export function StatusWidget({
  status,
  message,
  actionLabel,
  onAction,
  details,
}: StatusWidgetProps) {
  const statusColors = {
    ok: "bg-green-100 text-green-900 border-green-300",
    warning: "bg-yellow-100 text-yellow-900 border-yellow-300",
    error: "bg-red-100 text-red-900 border-red-300",
  }

  const statusDots = {
    ok: "bg-green-500",
    warning: "bg-yellow-500",
    error: "bg-red-500",
  }

  return (
    <div className={cn("p-4 rounded-lg border", statusColors[status])}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <div className={cn("w-2 h-2 rounded-full", statusDots[status])} />
            <span className="font-semibold text-sm">{message}</span>
          </div>
          {details && <div className="text-xs mt-2">{details}</div>}
        </div>
        {actionLabel && (
          <button
            onClick={onAction}
            className="shrink-0 text-xs font-medium underline hover:opacity-70 transition-opacity"
          >
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// summary: Short text block / custom content
// ============================================================================

interface SummaryWidgetProps {
  children: ReactNode
  label: string
}

export function SummaryWidget({ children, label }: SummaryWidgetProps) {
  return (
    <div className="space-y-2">
      <h3 className="font-semibold text-sm">{label}</h3>
      <div className="p-4 rounded-lg border bg-card text-sm">{children}</div>
    </div>
  )
}

// ============================================================================
// Widget section heading and layout
// ============================================================================

interface WidgetSectionProps {
  title: string
  children: ReactNode
  className?: string
}

export function WidgetSection({ title, children, className }: WidgetSectionProps) {
  return (
    <section className={cn("space-y-4", className)}>
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  )
}
