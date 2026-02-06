import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { streamChat } from "@/lib/sse"
import { toast } from "sonner"
import type { ChatMessage, PaginatedResponse, Thread } from "@/lib/types"

let msgCounter = 0
function nextId(): string {
  return `msg-${Date.now()}-${++msgCounter}`
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)
  const loadIdRef = useRef(0)

  const refreshThreads = useCallback(async () => {
    try {
      const res = await api.get<PaginatedResponse<Thread>>("/api/threads")
      setThreads(res.items)
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

      const userMsg: ChatMessage = { id: nextId(), role: "user", content: text }
      const assistantMsg: ChatMessage = { id: nextId(), role: "assistant", content: "" }
      setMessages((prev) => [...prev, userMsg, assistantMsg])
      setIsStreaming(true)

      controllerRef.current = streamChat(
        text,
        {
          onThread(threadId, title) {
            setActiveThreadId(threadId)
            setThreads((prev) => {
              if (prev.some((t) => t.id === threadId)) return prev
              return [
                {
                  id: threadId,
                  title: title || "New chat",
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
                ...prev,
              ]
            })
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
          onSources(sources) {
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last?.role === "assistant") {
                updated[updated.length - 1] = { ...last, sources }
              }
              return updated
            })
          },
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
      stop()
      setActiveThreadId(threadId)
      const currentLoad = ++loadIdRef.current
      try {
        const res = await api.get<{
          messages: Array<{ role: string; content: string; sources?: string[] | null }>
        }>(`/api/threads/${threadId}/messages`)
        if (currentLoad !== loadIdRef.current) return
        setMessages(
          res.messages.map((m) => ({
            id: nextId(),
            role: m.role as "user" | "assistant",
            content: m.content,
            ...(m.sources ? { sources: m.sources } : {}),
          })),
        )
      } catch (err) {
        if (currentLoad !== loadIdRef.current) return
        toast.error(`Failed to load thread: ${(err as Error).message}`)
        setMessages([])
      }
    },
    [stop],
  )

  const renameThread = useCallback(
    async (threadId: string, title: string) => {
      try {
        await api.patch(`/api/threads/${threadId}`, { title })
        setThreads((prev) =>
          prev.map((t) => (t.id === threadId ? { ...t, title } : t)),
        )
      } catch (err) {
        toast.error(`Failed to rename thread: ${(err as Error).message}`)
      }
    },
    [],
  )

  const deleteThread = useCallback(
    async (threadId: string) => {
      try {
        await api.del(`/api/threads/${threadId}`)
        if (activeThreadId === threadId) {
          setMessages([])
          setActiveThreadId(null)
        }
        await refreshThreads()
      } catch (err) {
        toast.error(`Failed to delete thread: ${(err as Error).message}`)
      }
    },
    [activeThreadId, refreshThreads],
  )

  const clear = useCallback(async () => {
    stop()
    setMessages([])
    setActiveThreadId(null)
    try {
      await api.del("/api/chat/history")
    } catch {
      // non-critical
    }
  }, [stop])

  const continueChat = useCallback(() => {
    send("Continue your previous response from where you left off.")
  }, [send])

  const savePlan = useCallback(async () => {
    try {
      const res = await api.post<{ message: string }>("/api/chat/save-plan", {
        history: messages,
      })
      return res.message
    } catch (err) {
      const msg = `Failed to save: ${(err as Error).message}`
      toast.error(msg)
      return msg
    }
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
    renameThread,
    deleteThread,
  }
}
