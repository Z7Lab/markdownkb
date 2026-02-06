import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { streamChat } from "@/lib/sse"
import type { ChatMessage, Thread } from "@/lib/types"

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)
  const loadIdRef = useRef(0)

  const refreshThreads = useCallback(async () => {
    try {
      const res = await api.get<{ threads: Thread[] }>("/api/threads")
      setThreads(res.threads)
    } catch {
      // Silently fail — threads list is non-critical
    }
  }, [])

  useEffect(() => {
    refreshThreads()
  }, [refreshThreads])

  const send = useCallback(
    (text: string) => {
      if (!text.trim() || isStreaming) return

      const userMsg: ChatMessage = { role: "user", content: text }
      setMessages((prev) => [
        ...prev,
        userMsg,
        { role: "assistant", content: "" },
      ])
      setIsStreaming(true)

      controllerRef.current = streamChat(
        text,
        {
          onThread(threadId, title) {
            setActiveThreadId(threadId)
            setThreads((prev) => [
              {
                id: threadId,
                title: title || "New chat",
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
              ...prev,
            ])
          },
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
          onSources() {},
          onDone() {
            setIsStreaming(false)
            controllerRef.current = null
            refreshThreads()
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
        },
        activeThreadId,
      )
    },
    [isStreaming, activeThreadId, refreshThreads],
  )

  const stop = useCallback(() => {
    controllerRef.current?.abort()
    setIsStreaming(false)
    controllerRef.current = null
  }, [])

  const newChat = useCallback(() => {
    stop()
    setMessages([])
    setActiveThreadId(null)
  }, [stop])

  const loadThread = useCallback(
    async (threadId: string) => {
      console.log(`[mdkb] Loading thread ${threadId}`)
      stop()
      setActiveThreadId(threadId)
      const currentLoad = ++loadIdRef.current
      try {
        const res = await api.get<{
          messages: Array<{ role: string; content: string }>
        }>(`/api/threads/${threadId}/messages`)
        // Guard against race: only apply if this is still the latest load
        if (currentLoad !== loadIdRef.current) return
        console.log(`[mdkb] Thread ${threadId}: ${res.messages.length} messages`)
        setMessages(
          res.messages.map((m) => ({
            role: m.role as "user" | "assistant",
            content: m.content,
          })),
        )
      } catch (err) {
        if (currentLoad !== loadIdRef.current) return
        console.error("[mdkb] Failed to load thread messages:", err)
        setMessages([])
      }
    },
    [stop],
  )

  const deleteThread = useCallback(
    async (threadId: string) => {
      await api.del(`/api/threads/${threadId}`)
      if (activeThreadId === threadId) {
        setMessages([])
        setActiveThreadId(null)
      }
      await refreshThreads()
    },
    [activeThreadId, refreshThreads],
  )

  const clear = useCallback(async () => {
    stop()
    setMessages([])
    setActiveThreadId(null)
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

  return {
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
  }
}
