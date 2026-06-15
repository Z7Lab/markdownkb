import { lazy, Suspense, type ComponentType } from "react"
import { useLocation, useRoute } from "wouter"
import { Tabs, TabsContent } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { ChatTab } from "@/components/chat/chat-tab"
import { DashboardTab } from "@/components/dashboard/dashboard-tab"
import { ErrorBoundary } from "@/components/error-boundary"
import { AppHeader } from "@/components/app-header"
import { SidebarShell } from "@/components/shell/sidebar-shell"
import { IndexEventProvider } from "@/hooks/use-index-events"
import { SettingsProvider } from "@/hooks/use-settings"
import { NavigationProvider } from "@/lib/navigation"
import { LayoutProvider, useLayout } from "@/lib/layout-context"
import { useVisibleRoutes } from "@/hooks/use-visible-routes"
import { routeToTab, tabToRoute } from "@/lib/routes"
import { AlertCircle } from "lucide-react"
import { SetupBanner } from "@/components/setup-banner"
import { LlmSetupNudge } from "@/components/llm-setup-nudge"
import { EmbeddingSetupNudge } from "@/components/embedding-setup-nudge"

const SearchTab = lazy(() => import("@/components/search/search-tab").then(m => ({ default: m.SearchTab })))
const FilesTab = lazy(() => import("@/components/browse/files-tab").then(m => ({ default: m.FilesTab })))
const PlannerTab = lazy(() => import("@/components/planner/planner-tab").then(m => ({ default: m.PlannerTab })))
const SettingsTab = lazy(() => import("@/components/settings/settings-tab").then(m => ({ default: m.SettingsTab })))
const VisualizationTab = lazy(() => import("@/components/visualization/visualization-tab").then(m => ({ default: m.VisualizationTab })))
const BucketsTab = lazy(() => import("@/components/buckets/buckets-tab").then(m => ({ default: m.BucketsTab })))
const WikiTab = lazy(() => import("@/components/wiki/wiki-tab").then(m => ({ default: m.WikiTab })))
const CurateTab = lazy(() => import("@/components/curate/curate-tab").then(m => ({ default: m.CurateTab })))
const ImportTab = lazy(() => import("@/components/import/import-tab").then(m => ({ default: m.ImportTab })))

function TabFallback() {
  return <div className="flex-1 flex items-center justify-center text-muted-foreground">Loading...</div>
}

const TAB_COMPONENTS: Record<string, ComponentType<Record<string, never>>> = {
  files: FilesTab,
  wiki: WikiTab,
  curate: CurateTab,
  import: ImportTab,
}

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

function AppInner() {
  const [location, setLocation] = useLocation()
  const [isChatThread, chatParams] = useRoute<{ threadId: string }>("/chat/:threadId")
  const [isSettingsSection, settingsParams] = useRoute<{ section: string }>("/settings/:section")
  const [isSearchResult, searchParams] = useRoute<{ searchId: string }>("/search/:searchId")
  const [isPlannerSession, plannerParams] = useRoute<{ planId: string }>("/planner/:planId")
  const [isBucketDetail, bucketParams] = useRoute<{ bucketId: string }>("/buckets/:bucketId")
  const { layout } = useLayout()
  const visibleRoutes = useVisibleRoutes()

  const pathname = location.split("?")[0] ?? "/"
  const isKnownRoute = pathname in routeToTab || isChatThread || isSettingsSection || isSearchResult || isPlannerSession || isBucketDetail
  const activeTab = isChatThread
    ? "chat"
    : isSettingsSection
    ? "settings"
    : isSearchResult
    ? "search"
    : isPlannerSession
    ? "planner"
    : isBucketDetail
    ? "buckets"
    : routeToTab[pathname] ?? null

  const showNotFound = !isKnownRoute

  const handleTabChange = (tab: string) => {
    const route = tabToRoute[tab]
    if (route) setLocation(route)
  }

  const tabContent = showNotFound ? (
    <NotFoundPage onGoHome={() => setLocation("/")} />
  ) : (
    <main
      id="main-content"
      className="flex-1 flex flex-col min-h-0 min-w-0"
      aria-label={`${(activeTab ?? "dashboard").charAt(0).toUpperCase() + (activeTab ?? "dashboard").slice(1)} tab content`}
    >
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
      <TabsContent value="search" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
        <ErrorBoundary fallbackMessage="Search encountered an error">
          <Suspense fallback={<TabFallback />}>
            <SearchTab defaultSearchId={searchParams?.searchId} />
          </Suspense>
        </ErrorBoundary>
      </TabsContent>
      <TabsContent value="planner" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
        <ErrorBoundary fallbackMessage="Planner encountered an error">
          <Suspense fallback={<TabFallback />}>
            <PlannerTab defaultPlanId={plannerParams?.planId} />
          </Suspense>
        </ErrorBoundary>
      </TabsContent>
      {Object.entries(TAB_COMPONENTS).map(([value, Component]) => (
        <TabsContent key={value} value={value} className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
          <ErrorBoundary fallbackMessage={`${value.charAt(0).toUpperCase() + value.slice(1)} encountered an error`}>
            <Suspense fallback={<TabFallback />}>
              <Component />
            </Suspense>
          </ErrorBoundary>
        </TabsContent>
      ))}
      <TabsContent value="buckets" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
        <ErrorBoundary fallbackMessage="Buckets encountered an error">
          <Suspense fallback={<TabFallback />}>
            <BucketsTab defaultBucketId={bucketParams?.bucketId} />
          </Suspense>
        </ErrorBoundary>
      </TabsContent>
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
      <TabsContent value="settings" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
        <ErrorBoundary fallbackMessage="Settings encountered an error">
          <Suspense fallback={<TabFallback />}>
            <SettingsTab initialSection={settingsParams?.section} />
          </Suspense>
        </ErrorBoundary>
      </TabsContent>
    </main>
  )

  return (
    <NavigationProvider value={{ setActiveTab: handleTabChange }}>
      <div className="h-screen flex flex-col overflow-hidden">
        <SetupBanner />
        <LlmSetupNudge onNavigateSettings={() => handleTabChange("settings")} />
        <EmbeddingSetupNudge onNavigateSettings={() => handleTabChange("settings")} />
        {layout === "sidebar" ? (
          <Tabs value={activeTab ?? "dashboard"} onValueChange={handleTabChange} orientation="vertical" className="flex-1 flex flex-row min-h-0">
            <SidebarShell
              routes={visibleRoutes}
              activeTab={activeTab}
              onNavigate={handleTabChange}
              onLogoClick={() => setLocation("/")}
              onSettingsClick={() => handleTabChange("settings")}
            />
            {tabContent}
          </Tabs>
        ) : (
          <Tabs value={activeTab ?? "dashboard"} onValueChange={handleTabChange} className="flex-1 flex flex-col min-h-0">
            <AppHeader
              routes={visibleRoutes}
              onLogoClick={() => setLocation("/")}
            />
            {tabContent}
          </Tabs>
        )}
      </div>
    </NavigationProvider>
  )
}

export function App() {
  return (
    <TooltipProvider delayDuration={300}>
      <SettingsProvider>
        <IndexEventProvider>
          <LayoutProvider>
            <AppInner />
          </LayoutProvider>
        </IndexEventProvider>
      </SettingsProvider>
    </TooltipProvider>
  )
}
