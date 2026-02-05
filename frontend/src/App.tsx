import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ChatTab } from "@/components/chat/chat-tab"
import { SearchTab } from "@/components/search/search-tab"
import { BrowseTab } from "@/components/browse/browse-tab"
import { SettingsTab } from "@/components/settings/settings-tab"
import { MessageSquare, Search, FolderOpen, Settings } from "lucide-react"

function App() {
  return (
    <div className="h-screen flex flex-col">
      <Tabs defaultValue="chat" className="flex-1 flex flex-col">
        <header className="border-b px-6 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold tracking-tight">mdkb</h1>
            <p className="text-xs text-muted-foreground">
              Knowledge base assistant
            </p>
          </div>
          <TabsList>
            <TabsTrigger value="chat">
              <MessageSquare className="h-4 w-4" />
              Chat
            </TabsTrigger>
            <TabsTrigger value="search">
              <Search className="h-4 w-4" />
              Search
            </TabsTrigger>
            <TabsTrigger value="browse">
              <FolderOpen className="h-4 w-4" />
              Browse
            </TabsTrigger>
            <TabsTrigger value="settings">
              <Settings className="h-4 w-4" />
              Settings
            </TabsTrigger>
          </TabsList>
        </header>

        <TabsContent value="chat" className="flex-1 mt-0">
          <ChatTab />
        </TabsContent>
        <TabsContent value="search" className="flex-1 mt-0">
          <SearchTab />
        </TabsContent>
        <TabsContent value="browse" className="flex-1 mt-0">
          <BrowseTab />
        </TabsContent>
        <TabsContent value="settings" className="flex-1 mt-0">
          <SettingsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default App
