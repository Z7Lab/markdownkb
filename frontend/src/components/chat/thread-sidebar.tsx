import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Plus, Trash2, MessageSquare } from "lucide-react";
import type { Thread } from "@/lib/types";
import { cn } from "@/lib/utils";

function relativeTime(iso: string): string {
  // SQLite datetime('now') gives "YYYY-MM-DD HH:MM:SS" — need "T" separator for valid ISO
  const ms = Date.now() - new Date(iso.replace(" ", "T") + "Z").getTime();
  const min = Math.floor(ms / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const d = Math.floor(hr / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(iso + "Z").toLocaleDateString();
}

export function ThreadSidebar({
  threads,
  activeThreadId,
  onNewChat,
  onLoadThread,
  onDeleteThread,
}: {
  threads: Thread[];
  activeThreadId: string | null;
  onNewChat: () => void;
  onLoadThread: (id: string) => void;
  onDeleteThread: (id: string) => void;
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
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-accent",
                activeThreadId === thread.id && "bg-accent",
              )}
              onClick={() => onLoadThread(thread.id)}
            >
              <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="flex-1 min-w-0 border border-orange-500 border-dashed" title={`DEBUG: title="${thread.title}" len=${thread.title?.length ?? 0}`}>
                <p
                  className="truncate font-medium bg-pink-500/20"
                  title={thread.title || "New chat"}
                >
                  {thread.title || "New chat"}
                </p>
                <p className="text-xs text-muted-foreground bg-cyan-500/20">
                  {relativeTime(thread.updated_at)}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0 text-muted-foreground/50 hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteThread(thread.id);
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
  );
}
