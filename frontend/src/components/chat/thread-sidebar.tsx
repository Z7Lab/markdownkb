import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Separator } from "@/components/ui/separator";
import { Plus, Trash2 } from "lucide-react";
import type { Thread } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ModelPicker } from "./model-picker";

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
  const [pendingDelete, setPendingDelete] = useState<Thread | null>(null);

  return (
    <div className="w-90 shrink-0 border-r flex flex-col min-h-0 overflow-hidden bg-muted/30">
      <div className="p-3 shrink-0 space-y-2">
        <ModelPicker />
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
      {/* NOTE: Using plain div instead of ScrollArea — Radix viewport caused persistent alignment issues */}
      <div className="flex-1 min-h-0 overflow-y-auto [scrollbar-width:thin]">
        <div className="p-3 space-y-2">
          {threads.map((thread) => (
            <div
              key={thread.id}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-accent",
                activeThreadId === thread.id &&
                  "bg-accent border-l-2 border-l-primary",
              )}
              onClick={() => onLoadThread(thread.id)}
            >
              <div className="flex-1 min-w-0 overflow-hidden">
                <p
                  className="truncate font-medium"
                  title={thread.title || "New chat"}
                >
                  {thread.title || "New chat"}
                </p>
                <p className="text-xs text-muted-foreground truncate">
                  {relativeTime(thread.updated_at)}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0 text-muted-foreground hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation();
                  setPendingDelete(thread);
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
          {threads.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">
              No conversations yet
            </p>
          )}
        </div>
      </div>
      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(open) => { if (!open) setPendingDelete(null); }}
        title="Delete conversation?"
        description={`This will permanently delete "${pendingDelete?.title || "New chat"}".`}
        confirmLabel="Delete"
        onConfirm={() => {
          if (pendingDelete) onDeleteThread(pendingDelete.id);
          setPendingDelete(null);
        }}
      />
    </div>
  );
}
