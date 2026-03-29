import { useChat } from "@/hooks/use-chat";
import { useScopes } from "@/hooks/use-scopes";
import { useTags } from "@/hooks/use-tags";
import { useSettings } from "@/hooks/use-settings";
import { useScopeTagFilter } from "@/hooks/use-scope-tag-filter";
import { useBuckets } from "@/hooks/use-buckets";
import { ChatControls } from "./chat-controls";
import { ChatInput } from "./chat-input";
import { ChatMessageList } from "./chat-message-list";
import { ChatSidebar } from "./chat-sidebar";

export function ChatTab() {
  const { scopes } = useScopes();
  const { tags: availableTags } = useTags();
  const { buckets } = useBuckets();
  const {
    selectedScopeIds, selectedTags,
    scopeIdsParam, adHocTagsParam,
    selectedBucketId,
    handleScopeChange, handleTagChange,
    handleBucketChange,
  } = useScopeTagFilter();

  const {
    messages,
    isStreaming,
    threads,
    activeThreadId,
    send,
    stop,
    clear,
    continueChat,
    savePlan,
    newChat,
    loadThread,
    renameThread,
    deleteThread,
  } = useChat(scopeIdsParam, adHocTagsParam, selectedBucketId);

  const { settings } = useSettings();
  const showDiagnostics = settings?.core?.diagnostics ?? false;

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <ChatSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        scopes={scopes}
        selectedScopeIds={selectedScopeIds}
        onScopeChange={handleScopeChange}
        availableTags={availableTags}
        selectedTags={selectedTags}
        onTagChange={handleTagChange}
        onNewChat={newChat}
        onLoadThread={loadThread}
        onRenameThread={renameThread}
        onDeleteThread={deleteThread}
        buckets={buckets}
        selectedBucketId={selectedBucketId}
        onBucketChange={handleBucketChange}
      />
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        <ChatMessageList
          messages={messages}
          isStreaming={isStreaming}
          showDiagnostics={showDiagnostics}
        />
        <div className="shrink-0 bg-background">
          <ChatControls
            onClear={clear}
            onContinue={continueChat}
            onSavePlan={savePlan}
            hasMessages={messages.length > 0}
          />
          <ChatInput onSend={send} onStop={stop} isStreaming={isStreaming} />
        </div>
      </div>
    </div>
  );
}
