import { lazy, Suspense, type ComponentType } from "react"
import { useLocation, useRoute } from "wouter"
import { Tabs, TabsContent } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { ChatTab } from "@/components/chat/chat-tab"
import { DashboardTab } from "@/components/dashboard/dashboard-tab"
import { ErrorBoundary } from "@/components/error-boundary"
import { AppHeader } from "@/components/app-header"
import { IndexEventProvider } from "@/hooks/use-index-events"
import { SettingsProvider } from "@/hooks/use-settings"
import { NavigationProvider } from "@/lib/navigation"
import { MessageSquare, Globe, FolderOpen, Lightbulb, Network, Share2, Database, BookOpen, LayoutDashboard, AlertCircle } from "lucide-react"
import { SetupBanner } from "@/components/setup-banner"
import { LlmSetupNudge } from "@/components/llm-setup-nudge"
import { EmbeddingSetupNudge } from "@/components/embedding-setup-nudge"
import type { LucideIcon } from "lucide-react"

const SearchTab = lazy(() => import("@/components/search/search-tab").then(m => ({ default: m.SearchTab })))
const FilesTab = lazy(() => import("@/components/browse/files-tab").then(m => ({ default: m.FilesTab })))
const PlannerTab = lazy(() => import("@/components/planner/planner-tab").then(m => ({ default: m.PlannerTab })))
const SettingsTab = lazy(() => import("@/components/settings/settings-tab").then(m => ({ default: m.SettingsTab })))
const VisualizationTab = lazy(() => import("@/components/visualization/visualization-tab").then(m => ({ default: m.VisualizationTab })))
const BucketsTab = lazy(() => import("@/components/buckets/buckets-tab").then(m => ({ default: m.BucketsTab })))
const WikiTab = lazy(() => import("@/components/wiki/wiki-tab").then(m => ({ default: m.WikiTab })))

function TabFallback() {
  return <div className="flex-1 flex items-center justify-center text-muted-foreground">Loading...</div>
}

// ── Single source of truth for routes/tabs ──────────────────────────────────

interface RouteEntry {
  value: string
  path: string
  icon: LucideIcon
  label: string
  pluginKey?: string
}

const ROUTE_CONFIG: RouteEntry[] = [
  { value: "dashboard", path: "/", icon: LayoutDashboard, label: "Home" },
  { value: "chat", path: "/chat", icon: MessageSquare, label: "Chat" },
  { value: "search", path: "/search", icon: Globe, label: "Search" },
  { value: "planner", path: "/planner", icon: Lightbulb, label: "Planner" },
  { value: "docmap", path: "/docmap", icon: Share2, label: "Doc Map", pluginKey: "docmap" },
  { value: "knowledge-graph", path: "/knowledge-graph", icon: Network, label: "Knowledge Graph", pluginKey: "knowledge_graph" },
  { value: "buckets", path: "/buckets", icon: Database, label: "Buckets", pluginKey: "buckets" },
  { value: "wiki", path: "/wiki", icon: BookOpen, label: "Wiki", pluginKey: "wiki_compile" },
  { value: "files", path: "/files", icon: FolderOpen, label: "Files" },
]

const routeToTab = Object.fromEntries(ROUTE_CONFIG.map(r => [r.path, r.value]))
const tabToRoute = Object.fromEntries(ROUTE_CONFIG.map(r => [r.value, r.path]))
// Settings tab isn't in the nav bar but needs route mapping
routeToTab["/settings"] = "settings"
tabToRoute["settings"] = "/settings"

// Tab content components — keyed by tab value. Entries without a component
// use the dashboard/chat eager-loaded paths or have special rendering below.
const TAB_COMPONENTS: Record<string, ComponentType<Record<string, never>>> = {
  search: SearchTab,
  planner: PlannerTab,
  files: FilesTab,
  buckets: BucketsTab,
  wiki: WikiTab,
}

// ── 404 page ────────────────────────────────────────────────────────────────

function NotFoundPage({ onGoHome }: { onGoHome: () => void }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center">
      <AlertCircle className="h-10 w-10 text-muted-foreground" />
      <div>
        <h2 className="text-lg font-semibold mb-1">Page not found</h2>
        <p className="text-sm text-muted-foreground">The page you're looking for doesn't exist.</p>
      </div>
      <button className="text-sm text-primary underline" onClick={onGoHome}>
        Go to dashboard
      </button>
    </div>
  )
}

// ── App ─────────────────────────────────────────────────────────────────────

export function App() {
  const [location, setLocation] = useLocation()
  const [isChatThread, chatParams] = useRoute<{ threadId: string }>("/chat/:threadId")
  const [isSettingsSection, settingsParams] = useRoute<{ section: string }>("/settings/:section")

  const isKnownRoute = location in routeToTab || isChatThread || isSettingsSection
  const activeTab = isChatThread
    ? "chat"
    : isSettingsSection
    ? "settings"
    : routeToTab[location] ?? null

  // Show 404 for unknown routes instead of silent redirect
  const showNotFound = !isKnownRoute

  const handleTabChange = (tab: string) => {
    const route = tabToRoute[tab]
    if (route) setLocation(route)
  }

  return (
    <TooltipProvider delayDuration={300}>
      <SettingsProvider>
        <IndexEventProvider>
        <NavigationProvider value={{ setActiveTab: handleTabChange }}>
          <div className="h-screen flex flex-col overflow-hidden">
            <SetupBanner />
            <LlmSetupNudge onNavigateSettings={() => handleTabChange("settings")} />
            <EmbeddingSetupNudge onNavigateSettings={() => handleTabChange("settings")} />
            <Tabs value={activeTab ?? "dashboard"} onValueChange={handleTabChange} className="flex-1 flex flex-col min-h-0">
              <AppHeader
                tabs={ROUTE_CONFIG}
                onLogoClick={() => setLocation("/")}
              />

              {showNotFound ? (
                <NotFoundPage onGoHome={() => setLocation("/")} />
              ) : (
                <main className="flex-1 flex flex-col min-h-0" aria-label={`${(activeTab ?? "dashboard").charAt(0).toUpperCase() + (activeTab ?? "dashboard").slice(1)} tab content`}>
                  {/* Eagerly loaded tabs */}
                  <TabsContent value="dashboard" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
                    <ErrorBoundary fallbackMessage="Dashboard encountered an error">
                      <DashboardTab />
                    </ErrorBoundary>
                  </TabsContent>
                  <TabsContent value="chat" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
                    <ErrorBoundary fallbackMessage="Chat encountered an error">
                      <ChatTab defaultThreadId={chatParams?.threadId} />
                    </ErrorBoundary>
                  </TabsContent>

                  {/* Lazily loaded standard tabs */}
                  {Object.entries(TAB_COMPONENTS).map(([value, Component]) => (
                    <TabsContent key={value} value={value} className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
                      <ErrorBoundary fallbackMessage={`${value.charAt(0).toUpperCase() + value.slice(1)} encountered an error`}>
                        <Suspense fallback={<TabFallback />}>
                          <Component />
                        </Suspense>
                      </ErrorBoundary>
                    </TabsContent>
                  ))}

                  {/* Visualization tabs share the same lazy component with different modes */}
                  <TabsContent value="docmap" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
                    <ErrorBoundary fallbackMessage="Doc Map encountered an error">
                      <Suspense fallback={<TabFallback />}>
                        <VisualizationTab fixedMode="similarity" />
                      </Suspense>
                    </ErrorBoundary>
                  </TabsContent>
                  <TabsContent value="knowledge-graph" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
                    <ErrorBoundary fallbackMessage="Knowledge Graph encountered an error">
                      <Suspense fallback={<TabFallback />}>
                        <VisualizationTab fixedMode="knowledge" />
                      </Suspense>
                    </ErrorBoundary>
                  </TabsContent>

                  {/* Settings tab has special props */}
                  <TabsContent value="settings" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
                    <ErrorBoundary fallbackMessage="Settings encountered an error">
                      <Suspense fallback={<TabFallback />}>
                        <SettingsTab initialSection={settingsParams?.section} />
                      </Suspense>
                    </ErrorBoundary>
                  </TabsContent>
                </main>
              )}
            </Tabs>
          </div>
        </NavigationProvider>
        </IndexEventProvider>
      </SettingsProvider>
    </TooltipProvider>
  )
}
