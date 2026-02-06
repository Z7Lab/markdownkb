import { useChat } from "@/hooks/use-chat";
import { useSettings } from "@/hooks/use-settings";
import { ChatControls } from "./chat-controls";
import { ChatInput } from "./chat-input";
import { MessageList } from "./message-list";
import { ThreadSidebar } from "./thread-sidebar";

export function ChatTab() {
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
  } = useChat();

  const { settings } = useSettings();
  const showDiagnostics = settings?.features?.diagnostics ?? false;

  return (
    <div className="flex flex-row h-full overflow-hidden">
      <ThreadSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onNewChat={newChat}
        onLoadThread={loadThread}
        onRenameThread={renameThread}
        onDeleteThread={deleteThread}
      />
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        <MessageList
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
