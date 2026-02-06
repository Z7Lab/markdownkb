import { useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { AppSidebar } from "@/components/ui/app-sidebar";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Pencil, Plus, Trash2 } from "lucide-react";
import type { Thread } from "@/lib/types";
import { cn, relativeTime } from "@/lib/utils";
import { ModelPicker } from "./model-picker";

export function ThreadSidebar({
  threads,
  activeThreadId,
  onNewChat,
  onLoadThread,
  onRenameThread,
  onDeleteThread,
}: {
  threads: Thread[];
  activeThreadId: string | null;
  onNewChat: () => void;
  onLoadThread: (id: string) => void;
  onRenameThread: (id: string, title: string) => void;
  onDeleteThread: (id: string) => void;
}) {
  const [pendingDelete, setPendingDelete] = useState<Thread | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function startRename(thread: Thread) {
    setEditingId(thread.id);
    setEditValue(thread.title || "");
    setTimeout(() => inputRef.current?.select(), 0);
  }

  function commitRename() {
    if (editingId && editValue.trim()) {
      onRenameThread(editingId, editValue.trim());
    }
    setEditingId(null);
  }

  function handleRenameKey(e: KeyboardEvent) {
    if (e.key === "Enter") commitRename();
    if (e.key === "Escape") setEditingId(null);
  }

  return (
    <AppSidebar
      header={
        <div className="space-y-2">
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
      }
    >
      <TooltipProvider delayDuration={400}>
        <div className="p-3 space-y-1" role="list">
          {threads.map((thread) => (
            <button
              key={thread.id}
              type="button"
              role="listitem"
              className={cn(
                "w-full text-left rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                activeThreadId === thread.id &&
                  "bg-accent border-l-2 border-l-primary",
              )}
              onClick={() => onLoadThread(thread.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onLoadThread(thread.id);
                }
              }}
            >
              {editingId === thread.id ? (
                <Input
                  ref={inputRef}
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={handleRenameKey}
                  onClick={(e) => e.stopPropagation()}
                  className="h-6 text-sm px-1 py-0"
                  autoFocus
                />
              ) : (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <p
                      className="font-medium overflow-hidden line-clamp-2"
                      onDoubleClick={(e) => {
                        e.stopPropagation();
                        startRename(thread);
                      }}
                    >
                      {thread.title || "New chat"}
                    </p>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-sm">
                    <p>{thread.title || "New chat"}</p>
                  </TooltipContent>
                </Tooltip>
              )}
              <div className="flex items-center gap-1 mt-0.5">
                <p className="text-xs text-muted-foreground flex-1 truncate">
                  {relativeTime(thread.updated_at)}
                </p>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Rename conversation"
                  className="h-5 w-5 shrink-0 text-muted-foreground hover:text-foreground"
                  onClick={(e) => {
                    e.stopPropagation();
                    startRename(thread);
                  }}
                >
                  <Pencil className="h-3 w-3" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Delete conversation"
                  className="h-5 w-5 shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    setPendingDelete(thread);
                  }}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            </button>
          ))}
          {threads.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">
              No conversations yet
            </p>
          )}
        </div>
      </TooltipProvider>
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
    </AppSidebar>
  );
}
