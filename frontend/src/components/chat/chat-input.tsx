import { useState, type KeyboardEvent } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Send, Square } from "lucide-react"

export function ChatInput({
  onSend,
  onStop,
  isStreaming,
}: {
  onSend: (text: string) => void
  onStop: () => void
  isStreaming: boolean
}) {
  const [input, setInput] = useState("")

  function handleSend() {
    if (!input.trim()) return
    onSend(input)
    setInput("")
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex gap-2 p-4 border-t border-2 border-lime-500 border-dashed bg-lime-500/10">
      <Textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask your knowledge base..."
        className="min-h-[44px] max-h-[120px] resize-none"
        rows={1}
      />
      {isStreaming ? (
        <Button onClick={onStop} variant="destructive" size="icon">
          <Square className="h-4 w-4" />
        </Button>
      ) : (
        <Button onClick={handleSend} size="icon" disabled={!input.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}
