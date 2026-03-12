import { useCallback, useEffect, useRef, useState } from "react"
import { api, retryWithBackoff } from "@/lib/api"
import { streamChat } from "@/lib/sse"
import { toast } from "sonner"
import { usePersistedState } from "@/hooks/use-persisted-state"
import type { ChatMessage, PaginatedResponse, Thread } from "@/lib/types"

function nextId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  // Fallback for non-secure contexts (HTTP over LAN)
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16)
  })
}

// LocalStorage key for streaming thread tracking (transient, not persisted state)
const STREAMING_THREAD_KEY = "mdkb_streaming_thread"

export function useChat(scopeIds?: string | null, adHocTags?: string[] | null) {
  const [messages, setMessages] = usePersistedState<ChatMessage[]>("mdkb_messages", [])
  const [isStreaming, setIsStreaming] = useState(false)
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = usePersistedState<string | null>("mdkb_active_thread", null)
  const controllerRef = useRef<AbortController | null>(null)
  const loadIdRef = useRef(0)
  const streamingThreadIdRef = useRef<string | null>(null) // Track which thread is streaming

  /** Shared cleanup for ending a stream (used by onDone, onError, stop) */
  const cleanupStream = useCallback(() => {
    setIsStreaming(false)
    controllerRef.current = null
    streamingThreadIdRef.current = null
    try { localStorage.removeItem(STREAMING_THREAD_KEY) } catch { /* ignore */ }
  }, [])

  // Restore streaming thread state on mount (transient — not managed by usePersistedState)
  useEffect(() => {
    try {
      const streamingThreadId = localStorage.getItem(STREAMING_THREAD_KEY)
      if (streamingThreadId) {
        streamingThreadIdRef.current = streamingThreadId || null
      }
    } catch {
      // ignore
    }
  }, [])

  const refreshThreads = useCallback(async (silent = false): Promise<boolean> => {
    try {
      const res = await api.get<PaginatedResponse<Thread>>("/api/threads")
      setThreads(res.items)
      return true
    } catch (err) {
      if (!silent) {
        toast.error(`Failed to load threads: ${(err as Error).message}`)
      }
      return false
    }
  }, [])

  // Load threads on mount with retry
  useEffect(() => {
    return retryWithBackoff(() => refreshThreads(true))
  }, [refreshThreads])

  const send = useCallback(
    (text: string) => {
      if (!text.trim() || isStreaming) return

      const userMsg: ChatMessage = { id: nextId(), role: "user", content: text }
      const assistantMsg: ChatMessage = { id: nextId(), role: "assistant", content: "" }
      setMessages((prev) => [...prev, userMsg, assistantMsg])
      setIsStreaming(true)

      // Track that this thread is streaming
      streamingThreadIdRef.current = activeThreadId
      try {
        localStorage.setItem(STREAMING_THREAD_KEY, activeThreadId || "")
      } catch {
        // ignore
      }

      controllerRef.current = streamChat(
        text,
        {
          onThread(threadId, title) {
            setActiveThreadId(threadId)
            streamingThreadIdRef.current = threadId
            try {
              localStorage.setItem(STREAMING_THREAD_KEY, threadId)
            } catch {
              // ignore
            }
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
            cleanupStream()
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
            cleanupStream()
          },
        },
        activeThreadId,
        scopeIds,
        adHocTags,
      )
    },
    [isStreaming, activeThreadId, refreshThreads, scopeIds, adHocTags, setMessages, setActiveThreadId, cleanupStream],
  )

  const stop = useCallback(() => {
    controllerRef.current?.abort()
    cleanupStream()
  }, [cleanupStream])

  const newChat = useCallback(() => {
    // Don't abort background stream if it's for a different thread
    if (streamingThreadIdRef.current === activeThreadId || streamingThreadIdRef.current === null) {
      stop()
    } else {
      setIsStreaming(false)
    }
    setMessages([])
    setActiveThreadId(null)
  }, [stop, activeThreadId, setMessages, setActiveThreadId])

  const loadThread = useCallback(
    async (threadId: string) => {
      const isStreamingThread = streamingThreadIdRef.current === threadId

      if (!isStreamingThread && isStreaming) {
        setIsStreaming(false)
      }

      if (!isStreamingThread) {
        if (activeThreadId === threadId) {
          stop()
        }
      }

      setActiveThreadId(threadId)
      const currentLoad = ++loadIdRef.current

      if (isStreamingThread) {
        setIsStreaming(true)
        return
      }

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
    [stop, isStreaming, activeThreadId, setMessages, setActiveThreadId],
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
        if (streamingThreadIdRef.current === threadId) {
          stop()
        }
        if (activeThreadId === threadId) {
          setMessages([])
          setActiveThreadId(null)
        }
        await refreshThreads()
      } catch (err) {
        toast.error(`Failed to delete thread: ${(err as Error).message}`)
      }
    },
    [activeThreadId, refreshThreads, stop, setMessages, setActiveThreadId],
  )

  const clear = useCallback(async () => {
    stop()
    setMessages([])
    setActiveThreadId(null)
    try {
      localStorage.removeItem(STREAMING_THREAD_KEY)
    } catch {
      // ignore
    }
    try {
      await api.del("/api/chat/history")
    } catch {
      /* server-side clear is best-effort; local state is already reset */
    }
  }, [stop, setMessages, setActiveThreadId])

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
