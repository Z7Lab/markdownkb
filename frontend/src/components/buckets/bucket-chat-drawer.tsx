import { useEffect, useState } from "react"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { X, Download, ChevronDown, FileText } from "lucide-react"
import { ChatMessageList } from "@/components/chat/chat-message-list"
import { ChatInput } from "@/components/chat/chat-input"
import { useBucketChat } from "@/hooks/use-bucket-chat"
import { useBucketFiles } from "@/hooks/use-buckets"
import { downloadMarkdown, cn } from "@/lib/utils"
import type { ChatMessage } from "@/lib/types"

function formatTranscript(bucketName: string, messages: ChatMessage[]): string {
  const date = new Date().toLocaleDateString()
  const lines = [`# Chat: ${bucketName} (${date})`, ""]
  for (const msg of messages) {
    if (!msg.content) continue
    lines.push(msg.role === "user" ? `**You:** ${msg.content}` : `**Assistant:** ${msg.content}`)
    lines.push("")
  }
  return lines.join("\n")
}

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
  const { files } = useBucketFiles(open ? bucketId : null)

  const [pickerOpen, setPickerOpen] = useState(false)
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set())

  // When files load, default to all selected
  useEffect(() => {
    if (files.length > 0) {
      setSelectedPaths(new Set(files.map((f) => f.path)))
    }
  }, [files])

  const allSelected = files.length > 0 && selectedPaths.size === files.length
  const activePaths = allSelected ? null : selectedPaths.size > 0 ? [...selectedPaths] : null

  function togglePath(path: string) {
    setSelectedPaths((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  function handleSend(text: string) {
    send(text, activePaths)
  }

  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <SheetContent side="right" className="w-[420px] sm:w-[520px] flex flex-col p-0 gap-0" showCloseButton={false}>
        <SheetHeader className="flex flex-row items-center justify-between px-4 py-3 border-b shrink-0">
          <SheetTitle className="text-sm font-medium truncate">{bucketName}</SheetTitle>
          <div className="flex items-center gap-0.5 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-foreground"
              onClick={() => downloadMarkdown(formatTranscript(bucketName, messages), `chat-${bucketName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`)}
              disabled={messages.length === 0}
              aria-label="Download transcript"
              title="Download transcript"
            >
              <Download className="h-3.5 w-3.5" />
            </Button>
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

        {/* File scope picker */}
        {files.length > 0 && (
          <div className="border-b shrink-0">
            <button
              className="w-full flex items-center justify-between px-4 py-2 text-xs text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors"
              onClick={() => setPickerOpen(!pickerOpen)}
              aria-expanded={pickerOpen}
            >
              <span className="flex items-center gap-1.5">
                <FileText className="h-3 w-3" />
                {allSelected ? `All ${files.length} files` : `${selectedPaths.size} of ${files.length} files`}
              </span>
              <ChevronDown className={cn("h-3 w-3 transition-transform duration-150", pickerOpen && "rotate-180")} />
            </button>

            {pickerOpen && (
              <div className="border-t">
                <div className="flex items-center justify-between px-4 py-1.5 border-b bg-muted/30">
                  <button
                    className="text-[10px] text-muted-foreground hover:text-foreground"
                    onClick={() => setSelectedPaths(new Set(files.map((f) => f.path)))}
                  >
                    Select all
                  </button>
                  <button
                    className="text-[10px] text-muted-foreground hover:text-foreground"
                    onClick={() => setSelectedPaths(new Set())}
                  >
                    Clear
                  </button>
                </div>
                <div className="max-h-48 overflow-y-auto">
                  {files.map((f) => (
                    <label
                      key={f.path}
                      className="flex items-center gap-2.5 px-4 py-1.5 hover:bg-accent cursor-pointer text-xs"
                    >
                      <input
                        type="checkbox"
                        className="shrink-0"
                        checked={selectedPaths.has(f.path)}
                        onChange={() => togglePath(f.path)}
                      />
                      <span className="truncate">{f.title || f.path.split("/").pop()}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="flex-1 min-h-0 overflow-y-auto">
          <ChatMessageList messages={messages} isStreaming={isStreaming} bucketId={bucketId} />
        </div>
        <div className="shrink-0 border-t p-3">
          <ChatInput onSend={handleSend} onStop={stop} isStreaming={isStreaming} />
        </div>
      </SheetContent>
    </Sheet>
  )
}
