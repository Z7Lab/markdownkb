import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ChatTab } from "@/components/chat/chat-tab"
import { SearchTab } from "@/components/search/search-tab"
import { BrowseTab } from "@/components/browse/browse-tab"
import { SettingsTab } from "@/components/settings/settings-tab"

function App() {
  return (
    <div className="h-screen flex flex-col">
      <header className="border-b px-6 py-3">
        <h1 className="text-xl font-bold">mdkb</h1>
        <p className="text-sm text-muted-foreground">
          Personal knowledge base assistant
        </p>
      </header>

      <Tabs defaultValue="chat" className="flex-1 flex flex-col">
        <TabsList className="mx-6 mt-2 w-fit">
          <TabsTrigger value="chat">Chat</TabsTrigger>
          <TabsTrigger value="search">Search</TabsTrigger>
          <TabsTrigger value="browse">Browse</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

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
