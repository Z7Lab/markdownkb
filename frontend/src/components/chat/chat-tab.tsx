import { useCallback, useEffect, useRef } from "react";
import { useLocation } from "wouter";
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
import { MessageSquare } from "lucide-react";
import { formatChatTranscript } from "@/lib/utils";

export function ChatTab({ defaultThreadId }: { defaultThreadId?: string }) {
  const [currentLocation, setLocation] = useLocation();
  const { scopes } = useScopes();
  const { tags: availableTags } = useTags();
  const { buckets } = useBuckets();
  const {
    selectedScopeIds, selectedTags,
    scopeIdsParam, adHocTagsParam,
    selectedBucketIds,
    bucketIdsParam,
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
    newChat,
    loadThread,
    renameThread,
    deleteThread,
  } = useChat(scopeIdsParam, adHocTagsParam, bucketIdsParam);

  const { settings } = useSettings();
  const showDiagnostics = settings?.core?.diagnostics ?? false;

  // Load thread from URL on mount / when deep-link param changes.
  // Use a ref so repeated renders with the same ID don't re-fire.
  const loadedThreadRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (defaultThreadId && defaultThreadId !== loadedThreadRef.current) {
      loadedThreadRef.current = defaultThreadId;
      loadThread(defaultThreadId);
    }
  }, [defaultThreadId, loadThread]);

  // Navigating to /chat without a thread ID should start a blank chat,
  // not silently restore the last persisted thread. Fires on mount and on
  // every navigation transition where the URL no longer pins a thread.
  useEffect(() => {
    if (!defaultThreadId && (activeThreadId || messages.length > 0)) {
      newChat();
    }
  }, [defaultThreadId]); // eslint-disable-line react-hooks/exhaustive-deps -- activeThreadId and messages.length are read for the condition but must not re-trigger; only URL changes should.

  // When the server assigns a thread ID mid-stream (onThread callback inside
  // useChat), push the URL so the thread is bookmarkable. Only fires when the
  // user is currently on a chat route — otherwise navigating away (e.g. Home)
  // would redirect back into the chat tab.
  useEffect(() => {
    if (!currentLocation.startsWith("/chat")) return;
    if (activeThreadId && activeThreadId !== defaultThreadId) {
      setLocation(`/chat/${activeThreadId}`, { replace: true });
    }
  }, [activeThreadId, defaultThreadId, setLocation, currentLocation]);

  // Keep URL in sync when the active thread changes via sidebar selection or new chat.
  // Wrap loadThread and newChat so they push the URL as a side-effect.
  const handleLoadThread = useCallback((id: string) => {
    loadThread(id);
    setLocation(`/chat/${id}`, { replace: true });
  }, [loadThread, setLocation]);

  const handleNewChat = useCallback(() => {
    newChat();
    setLocation("/chat", { replace: true });
  }, [newChat, setLocation]);

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
        onNewChat={handleNewChat}
        onLoadThread={handleLoadThread}
        onRenameThread={renameThread}
        onDeleteThread={deleteThread}
        buckets={buckets}
        selectedBucketIds={selectedBucketIds}
        onBucketChange={handleBucketChange}
      />
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        {messages.length > 0 && (
          <div className="shrink-0 border-b px-4 py-3 flex items-center gap-2">
            <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
            <h2 className="text-base font-semibold text-foreground truncate">
              {threads.find(t => t.id === activeThreadId)?.title ?? "Chat"}
            </h2>
          </div>
        )}
        <ChatMessageList
          messages={messages}
          isStreaming={isStreaming}
          showDiagnostics={showDiagnostics}
        />
        <div className="shrink-0 bg-background">
          <ChatControls
            onClear={clear}
            onContinue={continueChat}
            content={() => formatChatTranscript(threads.find(t => t.id === activeThreadId)?.title ?? "Chat", messages)}
            filename="chat-transcript"
            hasMessages={messages.length > 0}
          />
          <ChatInput onSend={send} onStop={stop} isStreaming={isStreaming} />
        </div>
      </div>
    </div>
  );
}
