import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Plus, Trash2, MessageSquare } from "lucide-react"
import type { Thread } from "@/lib/types"
import { cn } from "@/lib/utils"

function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso + "Z").getTime()
  const min = Math.floor(ms / 60000)
  if (min < 1) return "just now"
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const d = Math.floor(hr / 24)
  if (d < 30) return `${d}d ago`
  return new Date(iso + "Z").toLocaleDateString()
}

export function ThreadSidebar({
  threads,
  activeThreadId,
  onNewChat,
  onLoadThread,
  onDeleteThread,
}: {
  threads: Thread[]
  activeThreadId: string | null
  onNewChat: () => void
  onLoadThread: (id: string) => void
  onDeleteThread: (id: string) => void
}) {
  return (
    <div className="w-64 border-r flex flex-col bg-muted/30">
      <div className="p-3">
        <Button
          onClick={onNewChat}
          variant="outline"
          className="w-full justify-start gap-2"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>
      <Separator />
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {threads.map((thread) => (
            <div
              key={thread.id}
              className={cn(
                "group flex items-center gap-2 rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-accent",
                activeThreadId === thread.id && "bg-accent",
              )}
              onClick={() => onLoadThread(thread.id)}
            >
              <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="flex-1 min-w-0">
                <p className="truncate font-medium">
                  {thread.title || "New chat"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {relativeTime(thread.updated_at)}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 opacity-0 group-hover:opacity-100 shrink-0"
                onClick={(e) => {
                  e.stopPropagation()
                  onDeleteThread(thread.id)
                }}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          ))}
          {threads.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">
              No conversations yet
            </p>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
