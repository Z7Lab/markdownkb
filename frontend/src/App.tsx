import { lazy, Suspense } from "react"
import { useLocation } from "wouter"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { ChatTab } from "@/components/chat/chat-tab"
import { ErrorBoundary } from "@/components/error-boundary"
import { IndexActivityIndicator } from "@/components/index-activity-indicator"
import { LLMStatusIndicator } from "@/components/llm-status-indicator"
import { IndexEventProvider } from "@/hooks/use-index-events"
import { SettingsProvider, useSettings } from "@/hooks/use-settings"
import { NavigationProvider } from "@/lib/navigation"
import { MessageSquare, Globe, FolderOpen, Lightbulb, Network } from "lucide-react"

const SearchTab = lazy(() => import("@/components/search/search-tab").then(m => ({ default: m.SearchTab })))
const FilesTab = lazy(() => import("@/components/browse/files-tab").then(m => ({ default: m.FilesTab })))
const PlannerTab = lazy(() => import("@/components/planner/planner-tab").then(m => ({ default: m.PlannerTab })))
const SettingsTab = lazy(() => import("@/components/settings/settings-tab").then(m => ({ default: m.SettingsTab })))
const GraphTab = lazy(() => import("@/components/graph/graph-tab").then(m => ({ default: m.GraphTab })))

function TabFallback() {
  return <div className="flex-1 flex items-center justify-center text-muted-foreground">Loading...</div>
}

// Map routes to tab values
const routeToTab: Record<string, string> = {
  "/": "chat",
  "/search": "search",
  "/planner": "planner",
  "/graph": "graph",
  "/files": "files",
  "/settings": "settings",
}

const tabToRoute: Record<string, string> = {
  chat: "/",
  search: "/search",
  planner: "/planner",
  graph: "/graph",
  files: "/files",
  settings: "/settings",
}

function GraphTabTrigger() {
  const { settings } = useSettings()
  if (!settings?.features?.knowledge_graph) return null
  return (
    <TabsTrigger value="graph">
      <Network className="h-4 w-4" />
      Graph
    </TabsTrigger>
  )
}

export function App() {
  const [location, setLocation] = useLocation()
  const activeTab = routeToTab[location] || "chat"

  const handleTabChange = (tab: string) => {
    const route = tabToRoute[tab]
    if (route) {
      setLocation(route)
    }
  }

  return (
    <TooltipProvider delayDuration={300}>
      <SettingsProvider>
        <IndexEventProvider>
        <NavigationProvider value={{ setActiveTab: handleTabChange }}>
          <div className="h-screen flex flex-col overflow-hidden">
            <Tabs value={activeTab} onValueChange={handleTabChange} className="flex-1 flex flex-col min-h-0">
            <header className="shrink-0 z-20 bg-background border-b px-6 py-3 flex items-center justify-between">
              <div>
                <h1 className="text-lg font-bold tracking-tight">mdkb</h1>
                <p className="text-xs text-muted-foreground">
                  Knowledge base assistant
                </p>
              </div>
              <div className="flex items-center gap-4">
                <IndexActivityIndicator />
                <LLMStatusIndicator />
                <TabsList>
                <TabsTrigger value="chat">
                  <MessageSquare className="h-4 w-4" />
                  Chat
                </TabsTrigger>
                <TabsTrigger value="search">
                  <Globe className="h-4 w-4" />
                  Search
                </TabsTrigger>
                <TabsTrigger value="planner">
                  <Lightbulb className="h-4 w-4" />
                  Planner
                </TabsTrigger>
                <GraphTabTrigger />
                <TabsTrigger value="files">
                  <FolderOpen className="h-4 w-4" />
                  Files
                </TabsTrigger>
              </TabsList>
              </div>
            </header>

            <main className="flex-1 flex flex-col min-h-0">
              <TabsContent value="chat" forceMount className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
                <ErrorBoundary fallbackMessage="Chat encountered an error">
                  <ChatTab />
                </ErrorBoundary>
              </TabsContent>
              <TabsContent value="search" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
                <ErrorBoundary fallbackMessage="Search encountered an error">
                  <Suspense fallback={<TabFallback />}>
                    <SearchTab />
                  </Suspense>
                </ErrorBoundary>
              </TabsContent>
              <TabsContent value="planner" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
                <ErrorBoundary fallbackMessage="Planner encountered an error">
                  <Suspense fallback={<TabFallback />}>
                    <PlannerTab />
                  </Suspense>
                </ErrorBoundary>
              </TabsContent>
              <TabsContent value="graph" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
                <ErrorBoundary fallbackMessage="Graph encountered an error">
                  <Suspense fallback={<TabFallback />}>
                    <GraphTab />
                  </Suspense>
                </ErrorBoundary>
              </TabsContent>
              <TabsContent value="files" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
                <ErrorBoundary fallbackMessage="Files encountered an error">
                  <Suspense fallback={<TabFallback />}>
                    <FilesTab />
                  </Suspense>
                </ErrorBoundary>
              </TabsContent>
              <TabsContent value="settings" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
                <ErrorBoundary fallbackMessage="Settings encountered an error">
                  <Suspense fallback={<TabFallback />}>
                    <SettingsTab />
                  </Suspense>
                </ErrorBoundary>
              </TabsContent>
            </main>
            </Tabs>
          </div>
        </NavigationProvider>
        </IndexEventProvider>
      </SettingsProvider>
    </TooltipProvider>
  )
}

