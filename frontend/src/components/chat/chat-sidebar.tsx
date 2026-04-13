import { Button } from "@/components/ui/button";
import { AppSidebar } from "@/components/ui/app-sidebar";
import { SidebarItemList } from "@/components/ui/sidebar-item-list";
import { Bot, MessageSquare, Plus } from "lucide-react";
import type { Scope, Thread } from "@/lib/types";
import type { Bucket } from "@/hooks/use-buckets";
import { ModelPicker } from "./model-picker";
import { ScopeTagFilter } from "@/components/scope-tag-filter";
import { BucketSelector } from "@/components/bucket-selector";

function isAgentThread(t: Thread): boolean {
  return t.title?.startsWith("[agent]") ?? false
}

function displayTitle(t: Thread): string {
  if (isAgentThread(t)) return t.title.replace(/^\[agent\]\s*/, "")
  return t.title || "New chat"
}

export function ChatSidebar({
  threads,
  activeThreadId,
  scopes,
  selectedScopeIds,
  onScopeChange,
  availableTags,
  selectedTags,
  onTagChange,
  onNewChat,
  onLoadThread,
  onRenameThread,
  onDeleteThread,
  buckets,
  selectedBucketIds,
  onBucketChange,
}: {
  threads: Thread[];
  activeThreadId: string | null;
  scopes: Scope[];
  selectedScopeIds: Set<string>;
  onScopeChange: (ids: Set<string>) => void;
  availableTags: string[];
  selectedTags: Set<string>;
  onTagChange: (tags: Set<string>) => void;
  onNewChat: () => void;
  onLoadThread: (id: string) => void;
  onRenameThread: (id: string, title: string) => void;
  onDeleteThread: (id: string) => void;
  buckets: Bucket[];
  selectedBucketIds: Set<string>;
  onBucketChange: (ids: Set<string>) => void;
}) {
  return (
    <AppSidebar
      header={
        <div className="space-y-2">
          <Button
            onClick={onNewChat}
            variant="outline"
            className="w-full justify-start gap-2"
          >
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
          <ModelPicker />
          <ScopeTagFilter
            scopes={scopes}
            selectedScopeIds={selectedScopeIds}
            onScopeChange={onScopeChange}
            availableTags={availableTags}
            selectedTags={selectedTags}
            onTagChange={onTagChange}
            hasBucket={selectedBucketIds.size > 0}
          />
          <BucketSelector
            buckets={buckets}
            selectedBucketIds={selectedBucketIds}
            onBucketChange={onBucketChange}
          />
        </div>
      }
    >
      <SidebarItemList
        items={threads}
        activeId={activeThreadId}
        emptyMessage="No conversations yet"
        deleteTitle="Delete conversation?"
        deleteDescription={(t) => `This will permanently delete "${displayTitle(t)}".`}
        getLabel={displayTitle}
        getTime={(t) => t.updated_at}
        renderIcon={(t) =>
          isAgentThread(t) ? (
            <Bot className="h-3 w-3 shrink-0 text-muted-foreground" />
          ) : (
            <MessageSquare className="h-3 w-3 shrink-0 text-muted-foreground" />
          )
        }
        onSelect={(t) => onLoadThread(t.id)}
        onRename={onRenameThread}
        onDelete={onDeleteThread}
      />
    </AppSidebar>
  );
}
