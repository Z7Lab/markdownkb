import { useState } from "react"
import { Settings, ChevronLeft, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { useAppVersion } from "@/hooks/use-app-version"
import { ThemeToggle } from "@/components/theme-toggle"
import { IndexActivityIndicator } from "@/components/index-activity-indicator"
import { LLMStatusIndicator } from "@/components/llm-status-indicator"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { RouteEntry } from "@/lib/routes"

interface SidebarShellProps {
  routes: RouteEntry[]
  activeTab: string | null
  onNavigate: (tab: string) => void
  onLogoClick: () => void
  onSettingsClick: () => void
}

export function SidebarShell({
  routes,
  activeTab,
  onNavigate,
  onLogoClick,
  onSettingsClick,
}: SidebarShellProps) {
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem("mdkb-sidebar-collapsed") === "true"
  })
  const { version } = useAppVersion()

  const toggleCollapsed = () => {
    const next = !collapsed
    setCollapsed(next)
    localStorage.setItem("mdkb-sidebar-collapsed", String(next))
  }

  return (
    <aside
      className={cn(
        "shrink-0 border-r flex flex-col h-full bg-muted/20 transition-[width] duration-200 overflow-hidden",
        collapsed ? "w-14" : "w-52",
      )}
      aria-label="App navigation"
    >
      {/* Logo row */}
      <div className={cn(
        "flex items-center gap-2 px-2 py-2.5 shrink-0",
        collapsed ? "justify-center" : "justify-between",
      )}>
        <button
          onClick={onLogoClick}
          className="flex items-center gap-2 hover:opacity-70 transition-opacity min-w-0"
          aria-label="Go to dashboard"
        >
          <div className="shrink-0 h-7 w-7 rounded-md bg-primary/15 flex items-center justify-center text-primary font-bold text-sm select-none">
            M
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="text-sm font-bold tracking-tight leading-tight truncate">MarkdownKB</div>
              {version && (
                <div className="text-[10px] text-muted-foreground leading-tight">
                  v{version.current_version}
                  {version.install_method !== "native" && ` · ${version.install_method}`}
                </div>
              )}
            </div>
          )}
        </button>
        {!collapsed && (
          <div className="flex items-center gap-1 shrink-0">
            <IndexActivityIndicator />
            <LLMStatusIndicator />
          </div>
        )}
      </div>

      <div className="border-t mx-2 shrink-0" />

      {/* Nav items */}
      <nav className="flex-1 py-2 overflow-y-auto px-2 space-y-0.5" aria-label="Main navigation">
        {routes.map((route) => {
          const isActive = activeTab === route.value
          const btn = (
            <button
              key={route.value}
              onClick={() => onNavigate(route.value)}
              className={cn(
                "w-full flex items-center gap-3 px-2 py-2 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-accent text-accent-foreground font-medium"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                collapsed && "justify-center",
              )}
              aria-current={isActive ? "page" : undefined}
            >
              <route.icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span className="truncate">{route.label}</span>}
            </button>
          )

          if (collapsed) {
            return (
              <Tooltip key={route.value}>
                <TooltipTrigger asChild>{btn}</TooltipTrigger>
                <TooltipContent side="right">{route.label}</TooltipContent>
              </Tooltip>
            )
          }
          return btn
        })}
      </nav>

      <div className="border-t mx-2 shrink-0" />

      {/* Bottom: Settings, ThemeToggle, collapse toggle */}
      <div className="py-2 px-2 shrink-0 space-y-0.5">
        {collapsed ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={onSettingsClick}
                className="w-full flex justify-center items-center p-2 rounded-md text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors"
              >
                <Settings className="h-4 w-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">Settings</TooltipContent>
          </Tooltip>
        ) : (
          <button
            onClick={onSettingsClick}
            className="w-full flex items-center gap-3 px-2 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors"
          >
            <Settings className="h-4 w-4 shrink-0" />
            <span>Settings</span>
          </button>
        )}

        <div className={cn(
          "flex items-center px-2 py-1",
          collapsed ? "justify-center" : "justify-between",
        )}>
          {!collapsed && <span className="text-xs text-muted-foreground">Theme</span>}
          <ThemeToggle />
        </div>

        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={toggleCollapsed}
              className={cn(
                "w-full flex items-center px-2 py-1.5 rounded-md text-xs text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors",
                collapsed ? "justify-center" : "gap-2",
              )}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed
                ? <ChevronRight className="h-3.5 w-3.5" />
                : <><ChevronLeft className="h-3.5 w-3.5" /><span>Collapse</span></>
              }
            </button>
          </TooltipTrigger>
          {collapsed && <TooltipContent side="right">Expand</TooltipContent>}
        </Tooltip>
      </div>
    </aside>
  )
}
