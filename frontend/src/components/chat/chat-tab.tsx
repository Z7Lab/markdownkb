import { useChat } from "@/hooks/use-chat"
import { ChatControls } from "./chat-controls"
import { ChatInput } from "./chat-input"
import { MessageList } from "./message-list"

export function ChatTab() {
  const { messages, isStreaming, send, stop, clear, continueChat, savePlan } = useChat()

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <MessageList messages={messages} isStreaming={isStreaming} />
      <ChatControls
        onClear={clear}
        onContinue={continueChat}
        onSavePlan={savePlan}
        hasMessages={messages.length > 0}
      />
      <ChatInput onSend={send} onStop={stop} isStreaming={isStreaming} />
    </div>
  )
}
