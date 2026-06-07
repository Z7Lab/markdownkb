import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { ChatMessageList } from "@/components/chat/chat-message-list"
import { ChatInput } from "@/components/chat/chat-input"
import { DownloadButtons } from "@/components/ui/download-buttons"
import { useBucketChat } from "@/hooks/use-bucket-chat"
import { MessageSquare, Plus, Trash2 } from "lucide-react"
import { cn, relativeTime, formatChatTranscript } from "@/lib/utils"

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
    deleteThread,
  } = useBucketChat(bucketId)

  const safeFilename = `chat-${bucketName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`

  return (
    <div className="flex h-full overflow-hidden">
      {/* Thread history sidebar — only shown when there are prior conversations */}
      {threads.length > 0 && (
        <div className="w-44 border-r flex flex-col shrink-0">
          <div className="p-2 border-b">
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
          <ScrollArea className="flex-1">
            <div className="p-1 space-y-0.5">
              {threads.map((t) => (
                <div key={t.id} className="group relative">
                  <button
                    className={cn(
                      "w-full text-left px-2 py-1.5 rounded-sm text-xs hover:bg-accent transition-colors pr-6",
                      activeThreadId === t.id && "bg-accent",
                    )}
                    onClick={() => loadThread(t.id)}
                  >
                    <div className="flex items-center gap-1.5 min-w-0">
                      <MessageSquare className="h-3 w-3 shrink-0 text-muted-foreground" />
                      <span className="truncate">{t.title || "Chat"}</span>
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-0.5 pl-4">
                      {relativeTime(t.updated_at)}
                    </div>
                  </button>
                  <button
                    className="absolute right-1 top-1/2 -translate-y-1/2 p-0.5 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity"
                    onClick={(e) => {
                      e.stopPropagation()
                      void deleteThread(t.id)
                    }}
                    aria-label="Delete conversation"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}

      {/* Chat area */}
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        {/* Top bar: new chat (when no sidebar) + download */}
        {threads.length === 0 && (
          <div className="px-3 py-2 border-b flex items-center justify-between shrink-0">
            <span className="text-xs text-muted-foreground">No prior conversations</span>
          </div>
        )}
        {threads.length > 0 && messages.length > 0 && (
          <div className="px-3 py-2 border-b flex items-center justify-between shrink-0">
            <span className="text-xs font-medium truncate text-foreground/80">
              {threads.find((t) => t.id === activeThreadId)?.title ?? "New chat"}
            </span>
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
