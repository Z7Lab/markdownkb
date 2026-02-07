import { lazy, Suspense, useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { ChatTab } from "@/components/chat/chat-tab"
import { ErrorBoundary } from "@/components/error-boundary"
import { LLMStatusIndicator } from "@/components/llm-status-indicator"
import { SettingsProvider } from "@/hooks/use-settings"
import { NavigationProvider } from "@/lib/navigation"
import { MessageSquare, Globe, FolderOpen } from "lucide-react"

const SearchTab = lazy(() => import("@/components/search/search-tab").then(m => ({ default: m.SearchTab })))
const FilesTab = lazy(() => import("@/components/browse/files-tab").then(m => ({ default: m.FilesTab })))
const SettingsTab = lazy(() => import("@/components/settings/settings-tab").then(m => ({ default: m.SettingsTab })))

function TabFallback() {
  return <div className="flex-1 flex items-center justify-center text-muted-foreground">Loading...</div>
}

function App() {
  const [activeTab, setActiveTab] = useState("chat")

  return (
    <TooltipProvider delayDuration={300}>
      <SettingsProvider>
        <NavigationProvider value={{ setActiveTab }}>
          <div className="h-screen flex flex-col overflow-hidden">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
            <header className="shrink-0 z-20 bg-background border-b px-6 py-3 flex items-center justify-between">
              <div>
                <h1 className="text-lg font-bold tracking-tight">mdkb</h1>
                <p className="text-xs text-muted-foreground">
                  Knowledge base assistant
                </p>
              </div>
              <div className="flex items-center gap-4">
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
                <TabsTrigger value="browse">
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
              <TabsContent value="browse" className="flex-1 mt-0 overflow-hidden data-[state=inactive]:hidden">
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
      </SettingsProvider>
    </TooltipProvider>
  )
}

export default App
