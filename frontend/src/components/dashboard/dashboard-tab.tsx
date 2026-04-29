import { useEffect, useState } from "react"
import { useLocation } from "wouter"
import { useSettings } from "@/hooks/use-settings"
import { api } from "@/lib/api"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"
import { ActivityList, WidgetSection } from "@/components/dashboard/dashboard-widgets"
import { DashboardCharts, type DashboardChartsData } from "@/components/dashboard/dashboard-charts"
import {
  MessageSquare,
  Globe,
  FolderOpen,
  Lightbulb,
  BookOpen,
  Archive,
  Settings,
  HardDriveDownload,
} from "lucide-react"
import { cn } from "@/lib/utils"

function getRelativeTime(dateString: string | null): string {
  if (!dateString) return ""
  const date = new Date(dateString)
  const now = new Date()
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)
  if (seconds < 60) return "just now"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return date.toLocaleDateString()
}

interface FeatureCard {
  label: string
  description: string
  icon: React.ElementType
  route: string
  pluginKey?: string
  coreKey?: string
  alwaysShow?: boolean
}

const FEATURE_CARDS: FeatureCard[] = [
  { label: "Chat", description: "Ask questions and get answers grounded in your knowledge base.", icon: MessageSquare, route: "/chat", coreKey: "rag_chat" },
  { label: "Search", description: "Semantic + keyword search with AI-generated summaries.", icon: Globe, route: "/search", pluginKey: "search" },
  { label: "Wiki", description: "Managed wikis — browse pages, ingest sources, run lint.", icon: BookOpen, route: "/wiki", pluginKey: "wiki_compile" },
  { label: "Planner", description: "MCTS-based implementation planning and skill reviews.", icon: Lightbulb, route: "/planner", pluginKey: "planner" },
  { label: "Buckets", description: "Temporary scoped collections with independent vector storage.", icon: Archive, route: "/buckets", pluginKey: "buckets" },
  { label: "Files", description: "Browse, read, and manage indexed files.", icon: FolderOpen, route: "/files", alwaysShow: true },
  { label: "Settings", description: "Configure models, sources, plugins, and retrieval.", icon: Settings, route: "/settings", alwaysShow: true },
]

export function DashboardTab() {
  const [, setLocation] = useLocation()
  const { settings } = useSettings()
  const [fileCount, setFileCount] = useState<number | null>(null)
  const [threadCount, setThreadCount] = useState<number | null>(null)
  const [viewingFile, setViewingFile] = useState<string | null>(null)
  const [chartsData, setChartsData] = useState<DashboardChartsData | null>(null)

  const [recentThreads, setRecentThreads] = useState<Array<{ id: string; title: string; created_at: string }>>([])
  const [recentFiles, setRecentFiles] = useState<Array<{ path: string; indexed_at: string }>>([])
  const [recentSearches, setRecentSearches] = useState<Array<{ id: string; query: string; created_at: string }>>([])

  useEffect(() => {
    api.get<{ total: number }>("/api/v1/files?limit=1").then((r) => setFileCount(r.total)).catch(() => {})
    api.get<{ total: number }>("/api/v1/threads?limit=1").then((r) => setThreadCount(r.total)).catch(() => {})
    api.get<{ items: Array<{ id: string; title: string; created_at: string }> }>("/api/v1/threads?limit=5").then((r) => setRecentThreads(r.items)).catch(() => {})
    api.get<{ items: Array<{ path: string; indexed_at: string }> }>("/api/v1/files?limit=5&sort=indexed_at").then((r) => setRecentFiles(r.items)).catch(() => {})
    api.get<{ items: Array<{ id: string; query: string; created_at: string }> }>("/api/v1/searches?limit=5").then((r) => setRecentSearches(r.items)).catch(() => {})
    api.get<DashboardChartsData>("/api/v1/dashboard/charts").then(setChartsData).catch(() => {})
  }, [])

  const sourceCount = settings?.source_configs?.length ?? null

  const stats = [
    { label: "Sources", value: sourceCount ?? "—" },
    { label: "Indexed files", value: fileCount ?? "—" },
    { label: "Threads", value: threadCount ?? "—" },
  ]

  const visibleCards = FEATURE_CARDS.filter((c) => {
    if (c.alwaysShow) return true
    if (c.pluginKey) return !!settings?.plugins_enabled?.[c.pluginKey]
    if (c.coreKey) return settings?.core?.[c.coreKey] !== false
    return true
  })

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-8">

        {/* Header + stats */}
        <div className="flex items-start justify-between gap-6 flex-wrap">
          <div className="space-y-1">
            <h2 className="text-2xl font-bold tracking-tight">MarkdownKB</h2>
            <p className="text-sm text-muted-foreground">Chat with your docs. Everything is markdown, nothing is magic.</p>
          </div>
          <div className="flex gap-6 shrink-0">
            {stats.map((s) => (
              <div key={s.label} className="space-y-0.5 text-right">
                <p className="text-2xl font-semibold tabular-nums">{s.value}</p>
                <p className="text-xs text-muted-foreground">{s.label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Charts */}
        {chartsData && (
          <div className="space-y-4">
            <DashboardCharts data={chartsData} />
          </div>
        )}

        {/* Feature grid + Activity side by side on wide screens */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {visibleCards.map((card) => {
                const Icon = card.icon
                return (
                  <button
                    key={card.route}
                    onClick={() => setLocation(card.route)}
                    className={cn(
                      "text-left rounded-lg border bg-card p-4 space-y-1.5",
                      "hover:bg-accent hover:border-accent-foreground/20 transition-colors",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-primary" />
                      <span className="font-medium text-sm">{card.label}</span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">{card.description}</p>
                  </button>
                )
              })}
            </div>
          </div>

          {(recentThreads.length > 0 || recentFiles.length > 0 || recentSearches.length > 0) && (
            <div className="lg:col-span-1">
              <WidgetSection title="Recent Activity">
                <ActivityList
                  groups={[
                    ...(settings?.core?.rag_chat !== false ? [{
                      label: "Threads",
                      items: recentThreads.map((t) => ({
                        id: t.id,
                        label: t.title || "(Untitled thread)",
                        timestamp: getRelativeTime(t.created_at),
                        onClick: () => setLocation(`/chat/${t.id}`),
                      })),
                    }] : []),
                    {
                      label: "Indexed Files",
                      items: recentFiles.map((f) => ({
                        id: f.path,
                        label: f.path.split("/").pop() || f.path,
                        timestamp: getRelativeTime(f.indexed_at),
                        onClick: () => setViewingFile(f.path),
                      })),
                    },
                    ...(settings?.plugins_enabled?.search ? [{
                      label: "Searches",
                      items: recentSearches.map((s) => ({
                        id: s.id,
                        label: s.query,
                        timestamp: getRelativeTime(s.created_at),
                        onClick: () => setLocation(`/search/${s.id}`),
                      })),
                    }] : []),
                  ]}
                />
              </WidgetSection>
            </div>
          )}
        </div>

        {/* Quick-start hint when no sources */}
        {sourceCount === 0 && (
          <div className="rounded-lg border border-dashed p-5 flex items-start gap-3">
            <HardDriveDownload className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
            <div className="space-y-1">
              <p className="text-sm font-medium">No sources configured yet</p>
              <p className="text-xs text-muted-foreground">
                Add a directory under{" "}
                <button className="underline underline-offset-2 hover:text-foreground" onClick={() => setLocation("/settings/sources")}>
                  Settings → Sources
                </button>{" "}
                to start indexing your markdown files.
              </p>
            </div>
          </div>
        )}

      </div>

      <FileViewerDialog path={viewingFile} onClose={() => setViewingFile(null)} />
    </div>
  )
}
