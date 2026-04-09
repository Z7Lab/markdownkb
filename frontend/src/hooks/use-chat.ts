import { useCallback, useEffect, useRef, useState } from "react"
import { api, retryWithBackoff } from "@/lib/api"
import { streamChat } from "@/lib/sse"
import { toast } from "sonner"
import { usePersistedState } from "@/hooks/use-persisted-state"
import type { ChatMessage, PaginatedResponse, Thread } from "@/lib/types"

let idCounter = 0
function nextId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  // Counter-based fallback for non-secure contexts (HTTP over LAN).
  // Only needs to be unique within a browser session, not cryptographically random.
  return `msg-${Date.now()}-${++idCounter}`
}

// LocalStorage key for streaming thread tracking (transient, not persisted state)
const STREAMING_THREAD_KEY = "markdownkb_streaming_thread"

export function useChat(scopeIds?: string | null, adHocTags?: string[] | null, bucketId?: string | null) {
  const [messages, setMessages] = usePersistedState<ChatMessage[]>("markdownkb_messages", [])
  const [isStreaming, setIsStreaming] = useState(false)
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = usePersistedState<string | null>("markdownkb_active_thread", null)
  const controllerRef = useRef<AbortController | null>(null)
  const loadIdRef = useRef(0)
  const streamingThreadIdRef = useRef<string | null>(null) // Track which thread is streaming
  const streamContentRef = useRef("") // Mutable buffer for streaming tokens
  const flushTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  /** Flush buffered streaming content into React state */
  const flushStreamContent = useCallback(() => {
    const content = streamContentRef.current
    if (!content) return
    setMessages((prev) => {
      const last = prev[prev.length - 1]
      if (last?.role !== "assistant") return prev
      const updated = [...prev]
      updated[updated.length - 1] = { ...last, content }
      return updated
    })
  }, [setMessages])

  /** Shared cleanup for ending a stream (used by onDone, onError, stop) */
  const cleanupStream = useCallback(() => {
    if (flushTimerRef.current) {
      clearInterval(flushTimerRef.current)
      flushTimerRef.current = null
    }
    flushStreamContent()
    streamContentRef.current = ""
    setIsStreaming(false)
    controllerRef.current = null
    streamingThreadIdRef.current = null
    try { localStorage.removeItem(STREAMING_THREAD_KEY) } catch { /* ignore */ }
  }, [flushStreamContent])

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

      // Start a throttled flush timer for streaming tokens (~30fps)
      streamContentRef.current = ""
      flushTimerRef.current = setInterval(flushStreamContent, 33)

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
            // Append to mutable ref; flushed to state by interval timer
            streamContentRef.current += content
          },
          onSources(sources, sourceMap) {
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last?.role === "assistant") {
                updated[updated.length - 1] = {
                  ...last,
                  sources,
                  ...(sourceMap ? { sourceMap } : {}),
                }
              }
              return updated
            })
          },
          onDone(meta) {
            if (meta?.provider || meta?.model) {
              setMessages((prev) => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last?.role === "assistant") {
                  updated[updated.length - 1] = { ...last, provider: meta.provider, model: meta.model }
                }
                return updated
              })
            }
            cleanupStream()
            refreshThreads()
          },
          onError(error) {
            streamContentRef.current = `Error: ${error.message}`
            cleanupStream()
          },
        },
        activeThreadId,
        scopeIds,
        adHocTags,
        bucketId,
      )
    },
    [isStreaming, activeThreadId, refreshThreads, scopeIds, adHocTags, bucketId, setMessages, setActiveThreadId, cleanupStream, flushStreamContent],
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
          messages: Array<{ role: string; content: string; sources?: string[] | null; source_map?: Record<string, string> | null; provider?: string | null; model?: string | null }>
        }>(`/api/threads/${threadId}/messages`)
        if (currentLoad !== loadIdRef.current) return
        setMessages(
          res.messages.map((m) => ({
            id: nextId(),
            role: m.role as "user" | "assistant",
            content: m.content,
            ...(m.sources ? { sources: m.sources } : {}),
            ...(m.source_map ? { sourceMap: m.source_map } : {}),
            ...(m.provider ? { provider: m.provider } : {}),
            ...(m.model ? { model: m.model } : {}),
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
