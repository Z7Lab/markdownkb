import { useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Pencil, Plus, Trash2 } from "lucide-react";
import type { Thread } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ModelPicker } from "./model-picker";

function relativeTime(iso: string): string {
  // Normalize: SQLite gives "YYYY-MM-DD HH:MM:SS", JS gives "...T...Z"
  const normalized = iso.includes("T") ? iso : `${iso.replace(" ", "T")}Z`;
  const ms = Date.now() - new Date(normalized).getTime();
  if (Number.isNaN(ms)) return "";
  const min = Math.floor(ms / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const d = Math.floor(hr / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(normalized).toLocaleDateString();
}

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
        <TooltipProvider delayDuration={400}>
          <div className="p-3 space-y-1">
            {threads.map((thread) => (
              <div
                key={thread.id}
                className={cn(
                  "rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-accent",
                  activeThreadId === thread.id &&
                    "bg-accent border-l-2 border-l-primary",
                )}
                onClick={() => onLoadThread(thread.id)}
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
                        className="font-medium overflow-hidden"
                        style={{
                          display: "-webkit-box",
                          WebkitBoxOrient: "vertical",
                          WebkitLineClamp: 2,
                        }}
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
                    className="h-5 w-5 shrink-0 text-muted-foreground hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPendingDelete(thread);
                    }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            ))}
            {threads.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">
                No conversations yet
              </p>
            )}
          </div>
        </TooltipProvider>
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
