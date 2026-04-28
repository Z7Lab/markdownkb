import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { X } from "lucide-react"
import { ChatMessageList } from "@/components/chat/chat-message-list"
import { ChatInput } from "@/components/chat/chat-input"
import { DownloadButtons } from "@/components/ui/download-buttons"
import { useBucketChat } from "@/hooks/use-bucket-chat"
import { formatChatTranscript } from "@/lib/utils"

export function BucketChatDrawer({
  open,
  onClose,
  bucketId,
  bucketName,
}: {
  open: boolean
  onClose: () => void
  bucketId: string
  bucketName: string
}) {
  const { messages, isStreaming, send, stop } = useBucketChat(bucketId)
  const safeFilename = `chat-${bucketName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`

  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <SheetContent side="right" className="w-[420px] sm:w-[520px] flex flex-col p-0 gap-0" showCloseButton={false}>
        <SheetHeader className="flex flex-row items-center justify-between px-4 py-3 border-b shrink-0">
          <SheetTitle className="text-sm font-medium truncate">{bucketName}</SheetTitle>
          <div className="flex items-center gap-1 shrink-0">
            <DownloadButtons
              content={() => formatChatTranscript(`Chat: ${bucketName}`, messages)}
              filename={safeFilename}
              disabled={messages.length === 0}
              buttonClassName="h-7 px-2 text-xs"
            />
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-foreground"
              onClick={onClose}
              aria-label="Close chat"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        </SheetHeader>

        <div className="flex-1 min-h-0 overflow-y-auto">
          <ChatMessageList messages={messages} isStreaming={isStreaming} bucketId={bucketId} />
        </div>
        <div className="shrink-0 border-t p-3">
          <ChatInput onSend={send} onStop={stop} isStreaming={isStreaming} />
        </div>
      </SheetContent>
    </Sheet>
  )
}
