import type { LucideIcon } from "lucide-react"
import {
  Archive, BookOpen, FilePlus, FolderOpen, Globe, LayoutDashboard,
  Lightbulb, MessageSquare, Network, Share2,
} from "lucide-react"

export interface RouteEntry {
  value: string
  path: string
  icon: LucideIcon
  label: string
  pluginKey?: string
}

export const ROUTE_CONFIG: RouteEntry[] = [
  { value: "dashboard", path: "/",                  icon: LayoutDashboard, label: "Home" },
  { value: "chat",      path: "/chat",              icon: MessageSquare,   label: "Chat" },
  { value: "search",    path: "/search",            icon: Globe,           label: "Search" },
  { value: "planner",   path: "/planner",           icon: Lightbulb,       label: "Planner" },
  { value: "docmap",    path: "/docmap",            icon: Share2,          label: "Doc Map",         pluginKey: "docmap" },
  { value: "knowledge-graph", path: "/knowledge-graph", icon: Network,     label: "Knowledge Graph", pluginKey: "knowledge_graph" },
  { value: "buckets",   path: "/buckets",           icon: Archive,         label: "Buckets",         pluginKey: "buckets" },
  { value: "wiki",      path: "/wiki",              icon: BookOpen,        label: "Wiki",            pluginKey: "wiki_compile" },
  { value: "import",    path: "/import",            icon: FilePlus,        label: "Import",          pluginKey: "converter" },
  { value: "files",     path: "/files",             icon: FolderOpen,      label: "Files" },
]

export const routeToTab = Object.fromEntries(ROUTE_CONFIG.map(r => [r.path, r.value]))
export const tabToRoute = Object.fromEntries(ROUTE_CONFIG.map(r => [r.value, r.path]))
routeToTab["/settings"] = "settings"
tabToRoute["settings"] = "/settings"
