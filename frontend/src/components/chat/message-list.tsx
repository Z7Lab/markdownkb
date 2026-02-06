import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ChatMessage } from "@/lib/types";
import { MessageBubble } from "./message-bubble";

export function MessageList({
  messages,
  isStreaming,
  showDiagnostics = false,
}: {
  messages: ChatMessage[];
  isStreaming: boolean;
  showDiagnostics?: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 min-h-0 flex items-center justify-center text-muted-foreground">
        Ask your knowledge base a question to get started.
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1 min-h-0">
      <div className="space-y-4 p-4">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            showDiagnostics={showDiagnostics}
          />
        ))}
        {isStreaming && messages[messages.length - 1]?.content === "" && (
          <div className="flex justify-start">
            <div className="text-muted-foreground text-sm animate-pulse">
              Thinking...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
