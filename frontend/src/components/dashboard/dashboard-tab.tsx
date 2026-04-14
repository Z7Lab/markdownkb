import { useEffect, useState } from "react"
import { useLocation } from "wouter"
import { useSettings } from "@/hooks/use-settings"
import { api } from "@/lib/api"
import {
  MessageSquare,
  Globe,
  FolderOpen,
  Lightbulb,
  BookOpen,
  Database,
  Settings,
  HardDriveDownload,
} from "lucide-react"
import { cn } from "@/lib/utils"

interface Stat {
  label: string
  value: string | number
}

interface FeatureCard {
  label: string
  description: string
  icon: React.ElementType
  route: string
  pluginKey?: string   // hide when plugins_enabled[pluginKey] is false
  coreKey?: string     // hide when core[coreKey] is false
  alwaysShow?: boolean // ignore gating entirely
}

const FEATURE_CARDS: FeatureCard[] = [
  {
    label: "Chat",
    description: "Ask questions and get answers grounded in your knowledge base.",
    icon: MessageSquare,
    route: "/chat",
    coreKey: "rag_chat",
  },
  {
    label: "Search",
    description: "Semantic + keyword search with AI-generated summaries.",
    icon: Globe,
    route: "/search",
    pluginKey: "search",
  },
  {
    label: "Wiki",
    description: "Managed wikis — browse pages, ingest sources, run lint.",
    icon: BookOpen,
    route: "/wiki",
    pluginKey: "wiki_compile",
  },
  {
    label: "Planner",
    description: "MCTS-based implementation planning and skill reviews.",
    icon: Lightbulb,
    route: "/planner",
    pluginKey: "planner",
  },
  {
    label: "Buckets",
    description: "Temporary scoped collections with independent vector storage.",
    icon: Database,
    route: "/buckets",
    pluginKey: "buckets",
  },
  {
    label: "Files",
    description: "Browse, read, and manage indexed files.",
    icon: FolderOpen,
    route: "/files",
    alwaysShow: true,
  },
  {
    label: "Settings",
    description: "Configure models, sources, plugins, and retrieval.",
    icon: Settings,
    route: "/settings",
    alwaysShow: true,
  },
]

export function DashboardTab() {
  const [, setLocation] = useLocation()
  const { settings } = useSettings()
  const [fileCount, setFileCount] = useState<number | null>(null)
  const [threadCount, setThreadCount] = useState<number | null>(null)

  useEffect(() => {
    api.get<{ total: number }>("/api/files?limit=1")
      .then((r) => setFileCount(r.total))
      .catch(() => {})
    api.get<{ total: number }>("/api/threads?limit=1")
      .then((r) => setThreadCount(r.total))
      .catch(() => {})
  }, [])

  const sourceCount = settings?.source_configs?.length ?? null

  const stats: Stat[] = [
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
    <div className="flex-1 overflow-auto">
      <div className="max-w-3xl mx-auto px-6 py-10 space-y-10">

        {/* Header */}
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-tight">MarkdownKB</h2>
          <p className="text-sm text-muted-foreground">
            Chat with your docs. Everything is markdown, nothing is magic.
          </p>
        </div>

        {/* Stats row */}
        <div className="flex gap-6">
          {stats.map((s) => (
            <div key={s.label} className="space-y-0.5">
              <p className="text-2xl font-semibold tabular-nums">{s.value}</p>
              <p className="text-xs text-muted-foreground">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Feature grid */}
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
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {card.description}
                </p>
              </button>
            )
          })}
        </div>

        {/* Quick-start hint when no sources */}
        {sourceCount === 0 && (
          <div className="rounded-lg border border-dashed p-5 flex items-start gap-3">
            <HardDriveDownload className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
            <div className="space-y-1">
              <p className="text-sm font-medium">No sources configured yet</p>
              <p className="text-xs text-muted-foreground">
                Add a directory under{" "}
                <button
                  className="underline underline-offset-2 hover:text-foreground"
                  onClick={() => setLocation("/settings/sources")}
                >
                  Settings → Sources
                </button>{" "}
                to start indexing your markdown files.
              </p>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
