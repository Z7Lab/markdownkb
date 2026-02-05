import { useChat } from "@/hooks/use-chat"
import { ChatControls } from "./chat-controls"
import { ChatInput } from "./chat-input"
import { MessageList } from "./message-list"
import { ThreadSidebar } from "./thread-sidebar"

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
    deleteThread,
  } = useChat()

  return (
    <div className="flex flex-row h-[calc(100vh-4.5rem)]">
      <ThreadSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onNewChat={newChat}
        onLoadThread={loadThread}
        onDeleteThread={deleteThread}
      />
      <div className="flex flex-col flex-1 min-w-0">
        <MessageList messages={messages} isStreaming={isStreaming} />
        <ChatControls
          onClear={clear}
          onContinue={continueChat}
          onSavePlan={savePlan}
          hasMessages={messages.length > 0}
        />
        <ChatInput onSend={send} onStop={stop} isStreaming={isStreaming} />
      </div>
    </div>
  )
}
