import { useEffect, useRef, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog";
import type { ChatMessage } from "@/lib/types";
import { ChatMessage as ChatMessageComponent } from "./chat-message";

export function ChatMessageList({
  messages,
  isStreaming,
  showDiagnostics = false,
}: {
  messages: ChatMessage[];
  isStreaming: boolean;
  showDiagnostics?: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [viewingFile, setViewingFile] = useState<string | null>(null);

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
    <>
      <ScrollArea className="flex-1 min-h-0">
        <div className="w-0 min-w-full space-y-4 p-4" role="log" aria-label="Chat messages">
          {messages.map((msg) => (
            <ChatMessageComponent
              key={msg.id}
              message={msg}
              showDiagnostics={showDiagnostics}
              onViewFile={setViewingFile}
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
      <FileViewerDialog path={viewingFile} onClose={() => setViewingFile(null)} />
    </>
  );
}
