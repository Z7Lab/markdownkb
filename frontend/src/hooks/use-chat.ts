import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { streamChat } from "@/lib/sse"
import { toast } from "sonner"
import type { ChatMessage, PaginatedResponse, Thread } from "@/lib/types"

function nextId(): string {
  return crypto.randomUUID()
}

// LocalStorage keys for persistence
const STORAGE_KEYS = {
  ACTIVE_THREAD: "mdkb_active_thread",
  MESSAGES: "mdkb_messages",
  STREAMING_THREAD: "mdkb_streaming_thread",
} as const

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)
  const loadIdRef = useRef(0)
  const streamingThreadIdRef = useRef<string | null>(null) // Track which thread is streaming
  const hasRestoredRef = useRef(false) // Prevent double restoration

  // Save current state to localStorage for persistence
  const saveState = useCallback((msgs: ChatMessage[], threadId: string | null) => {
    try {
      localStorage.setItem(STORAGE_KEYS.MESSAGES, JSON.stringify(msgs))
      localStorage.setItem(STORAGE_KEYS.ACTIVE_THREAD, threadId || "")
    } catch (err) {
      console.warn("Failed to save chat state:", err)
    }
  }, [])

  // Restore state from localStorage
  const restoreState = useCallback(() => {
    if (hasRestoredRef.current) return
    hasRestoredRef.current = true

    try {
      const savedMessages = localStorage.getItem(STORAGE_KEYS.MESSAGES)
      const savedThreadId = localStorage.getItem(STORAGE_KEYS.ACTIVE_THREAD)
      const streamingThreadId = localStorage.getItem(STORAGE_KEYS.STREAMING_THREAD)

      if (savedMessages) {
        const msgs = JSON.parse(savedMessages) as ChatMessage[]
        if (msgs.length > 0) {
          setMessages(msgs)
        }
      }

      if (savedThreadId) {
        setActiveThreadId(savedThreadId || null)
      }

      if (streamingThreadId) {
        streamingThreadIdRef.current = streamingThreadId || null
      }
    } catch (err) {
      console.warn("Failed to restore chat state:", err)
    }
  }, [])

  const refreshThreads = useCallback(async (silent = false): Promise<boolean> => {
    try {
      const res = await api.get<PaginatedResponse<Thread>>("/api/threads")
      setThreads(res.items)
      return true
    } catch (err) {
      if (!silent) {
        console.warn("Failed to load threads:", err)
      }
      return false
    }
  }, [])

  // Restore state on mount and refresh threads with retry
  useEffect(() => {
    restoreState()

    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let retryCount = 0
    const MAX_RETRIES = 10

    const loadWithRetry = async () => {
      const success = await refreshThreads(true) // silent = true

      // If load failed and we haven't exceeded max retries, retry in 2 seconds
      if (!success && retryCount < MAX_RETRIES) {
        retryCount++
        retryTimer = setTimeout(loadWithRetry, 2000)
      }
    }

    loadWithRetry()

    return () => {
      if (retryTimer) clearTimeout(retryTimer)
    }
    // Only run on mount - deliberately excluding dependencies to prevent retry loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run on mount

  // Auto-save state whenever messages or activeThreadId changes
  useEffect(() => {
    if (hasRestoredRef.current) {
      saveState(messages, activeThreadId)
    }
  }, [messages, activeThreadId, saveState])

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
        localStorage.setItem(STORAGE_KEYS.STREAMING_THREAD, activeThreadId || "")
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
              localStorage.setItem(STORAGE_KEYS.STREAMING_THREAD, threadId)
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
            setIsStreaming(false)
            controllerRef.current = null
            streamingThreadIdRef.current = null
            try {
              localStorage.removeItem(STORAGE_KEYS.STREAMING_THREAD)
            } catch {
              // ignore
            }
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
            streamingThreadIdRef.current = null
            try {
              localStorage.removeItem(STORAGE_KEYS.STREAMING_THREAD)
            } catch {
              // ignore
            }
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
    streamingThreadIdRef.current = null
    try {
      localStorage.removeItem(STORAGE_KEYS.STREAMING_THREAD)
    } catch {
      // ignore
    }
  }, [])

  const newChat = useCallback(() => {
    // Don't abort background stream if it's for a different thread
    // Only stop if we're viewing the streaming thread
    if (streamingThreadIdRef.current === activeThreadId || streamingThreadIdRef.current === null) {
      stop()
    } else {
      // Let background stream continue
      setIsStreaming(false)
    }
    setMessages([])
    setActiveThreadId(null)
  }, [stop, activeThreadId])

  const loadThread = useCallback(
    async (threadId: string) => {
      // Check if we're switching back to a thread that's currently streaming
      const isStreamingThread = streamingThreadIdRef.current === threadId

      // If we're loading a different thread (not the streaming one), don't stop the stream
      // Let it complete in the background
      if (!isStreamingThread && isStreaming) {
        // Stream will continue in background for the other thread
        setIsStreaming(false) // Hide streaming UI for current view
      }

      // If loading the actively streaming thread, don't stop it
      if (!isStreamingThread) {
        // Only stop if we're not going back to the streaming thread
        if (activeThreadId === threadId) {
          stop() // Only stop if clicking the same thread (refresh)
        }
      }

      setActiveThreadId(threadId)
      const currentLoad = ++loadIdRef.current

      // If this is the streaming thread, show streaming state and current messages
      if (isStreamingThread) {
        setIsStreaming(true)
        return // Keep current messages, don't reload from API
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
    [stop, isStreaming, activeThreadId],
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
        // If deleting the streaming thread, abort it
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
    [activeThreadId, refreshThreads, stop],
  )

  const clear = useCallback(async () => {
    stop()
    setMessages([])
    setActiveThreadId(null)
    // Clear localStorage
    try {
      localStorage.removeItem(STORAGE_KEYS.MESSAGES)
      localStorage.removeItem(STORAGE_KEYS.ACTIVE_THREAD)
      localStorage.removeItem(STORAGE_KEYS.STREAMING_THREAD)
    } catch {
      // ignore
    }
    try {
      await api.del("/api/chat/history")
    } catch (err) {
      console.warn("Failed to clear chat history on server:", err)
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
