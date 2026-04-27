import { useSettings } from "@/hooks/use-settings"
import { ROUTE_CONFIG, type RouteEntry } from "@/lib/routes"

export function useVisibleRoutes(): RouteEntry[] {
  const { settings } = useSettings()
  const plugins = settings?.plugins_enabled as Record<string, boolean> | undefined
  return ROUTE_CONFIG.filter(route => {
    if (!route.pluginKey) return true
    return plugins?.[route.pluginKey] ?? false
  })
}
