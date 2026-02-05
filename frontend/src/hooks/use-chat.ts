import { useCallback, useRef, useState } from "react"
import { api } from "@/lib/api"
import { streamChat } from "@/lib/sse"
import type { ChatMessage } from "@/lib/types"

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const controllerRef = useRef<AbortController | null>(null)

  const send = useCallback((text: string) => {
    if (!text.trim() || isStreaming) return

    const userMsg: ChatMessage = { role: "user", content: text }
    setMessages((prev) => [...prev, userMsg, { role: "assistant", content: "" }])
    setIsStreaming(true)

    controllerRef.current = streamChat(text, {
      onToken(content) {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: last.content + content,
            }
          }
          return updated
        })
      },
      onSources() {
        // Sources are already appended inline by the backend
      },
      onDone() {
        setIsStreaming(false)
        controllerRef.current = null
      },
      onError(error) {
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: `Error: ${error.message}`,
            }
          }
          return updated
        })
        setIsStreaming(false)
        controllerRef.current = null
      },
    })
  }, [isStreaming])

  const stop = useCallback(() => {
    controllerRef.current?.abort()
    setIsStreaming(false)
    controllerRef.current = null
  }, [])

  const clear = useCallback(async () => {
    stop()
    setMessages([])
    await api.del("/api/chat/history")
  }, [stop])

  const continueChat = useCallback(() => {
    send("Continue your previous response from where you left off.")
  }, [send])

  const savePlan = useCallback(async () => {
    const res = await api.post<{ message: string }>("/api/chat/save-plan", {
      history: messages,
    })
    return res.message
  }, [messages])

  return { messages, isStreaming, send, stop, clear, continueChat, savePlan }
}
