import { Button } from "@/components/ui/button"
import { ChatMessageList } from "@/components/chat/chat-message-list"
import { ChatInput } from "@/components/chat/chat-input"
import { DownloadButtons } from "@/components/ui/download-buttons"
import { SidebarItemList } from "@/components/ui/sidebar-item-list"
import { useBucketChat } from "@/hooks/use-bucket-chat"
import { MessageSquare, Plus } from "lucide-react"
import { formatChatTranscript } from "@/lib/utils"

export function BucketChatSection({
  bucketId,
  bucketName,
}: {
  bucketId: string
  bucketName: string
}) {
  const {
    messages,
    isStreaming,
    send,
    stop,
    threads,
    activeThreadId,
    newChat,
    loadThread,
    renameThread,
    deleteThread,
  } = useBucketChat(bucketId)

  const safeFilename = `chat-${bucketName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`
  const activeTitle = threads.find((t) => t.id === activeThreadId)?.title ?? "New chat"

  return (
    <div className="flex h-full overflow-hidden">
      {/* Conversation history — reuses the Chat tab's list (search, tooltip, rename, delete) */}
      {threads.length > 0 && (
        <div className="w-56 border-r flex flex-col shrink-0 min-h-0">
          <div className="p-2 border-b shrink-0">
            <Button
              variant="outline"
              size="sm"
              className="w-full gap-1 h-7 text-xs"
              onClick={newChat}
            >
              <Plus className="h-3 w-3" />
              New chat
            </Button>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto">
            <SidebarItemList
              items={threads}
              activeId={activeThreadId}
              emptyMessage="No conversations yet"
              deleteTitle="Delete conversation?"
              deleteDescription={(t) => `This will permanently delete "${t.title || "this conversation"}".`}
              getLabel={(t) => t.title || "Chat"}
              getTime={(t) => t.updated_at}
              renderIcon={() => <MessageSquare className="h-3 w-3 shrink-0 text-muted-foreground" />}
              onSelect={(t) => loadThread(t.id)}
              onRename={(id, label) => void renameThread(id, label)}
              onDelete={(id) => void deleteThread(id)}
            />
          </div>
        </div>
      )}

      {/* Chat area */}
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        {threads.length > 0 && messages.length > 0 && (
          <div className="px-3 py-2 border-b flex items-center justify-between shrink-0">
            <span className="text-xs font-medium truncate text-foreground/80">{activeTitle}</span>
            <DownloadButtons
              content={() => formatChatTranscript(`Chat: ${bucketName}`, messages)}
              filename={safeFilename}
              disabled={messages.length === 0}
              buttonClassName="h-6 px-2 text-xs"
            />
          </div>
        )}

        <div className="flex-1 min-h-0 overflow-y-auto">
          <ChatMessageList messages={messages} isStreaming={isStreaming} bucketId={bucketId} />
        </div>
        <div className="shrink-0 border-t p-3">
          <ChatInput onSend={send} onStop={stop} isStreaming={isStreaming} />
        </div>
      </div>
    </div>
  )
}
