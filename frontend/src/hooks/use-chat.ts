import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { streamChat } from "@/lib/sse"
import { toast } from "sonner"
import { usePersistedState } from "@/hooks/use-persisted-state"
import { useThreads } from "@/hooks/use-threads"
import type { ChatMessage } from "@/lib/types"

let idCounter = 0
function nextId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `msg-${Date.now()}-${++idCounter}`
}

const STREAMING_THREAD_KEY = "markdownkb_streaming_thread"

export function useChat(scopeIds?: string | null, adHocTags?: string[] | null, bucketIds?: string | null) {
  const [messages, setMessages] = usePersistedState<ChatMessage[]>("markdownkb_messages", [])
  const [isStreaming, setIsStreaming] = useState(false)
  const [activeThreadId, setActiveThreadId] = usePersistedState<string | null>("markdownkb_active_thread", null)
  const controllerRef = useRef<AbortController | null>(null)
  const loadIdRef = useRef(0)
  const streamingThreadIdRef = useRef<string | null>(null)
  const streamContentRef = useRef("")
  const flushTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const { threads, refreshThreads, renameThread, deleteThread: removeThread, addOptimistic } = useThreads()

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

  const send = useCallback(
    (text: string) => {
      if (!text.trim() || isStreaming) return

      const userMsg: ChatMessage = { id: nextId(), role: "user", content: text }
      const assistantMsg: ChatMessage = { id: nextId(), role: "assistant", content: "" }
      setMessages((prev) => [...prev, userMsg, assistantMsg])
      setIsStreaming(true)

      streamingThreadIdRef.current = activeThreadId
      try { localStorage.setItem(STREAMING_THREAD_KEY, activeThreadId || "") } catch { /* ignore */ }

      streamContentRef.current = ""
      flushTimerRef.current = setInterval(flushStreamContent, 33)

      controllerRef.current = streamChat(
        text,
        {
          onThread(threadId, title) {
            setActiveThreadId(threadId)
            streamingThreadIdRef.current = threadId
            try { localStorage.setItem(STREAMING_THREAD_KEY, threadId) } catch { /* ignore */ }
            addOptimistic({
              id: threadId,
              title: title || "New chat",
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            })
          },
          onToken(content) {
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
        bucketIds,
      )
    },
    [isStreaming, activeThreadId, refreshThreads, scopeIds, adHocTags, bucketIds, setMessages, setActiveThreadId, cleanupStream, flushStreamContent, addOptimistic],
  )

  const stop = useCallback(() => {
    controllerRef.current?.abort()
    cleanupStream()
  }, [cleanupStream])

  const newChat = useCallback(() => {
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
        }>(`/api/v1/threads/${threadId}/messages`)
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

  const deleteThread = useCallback(
    async (threadId: string) => {
      if (streamingThreadIdRef.current === threadId) stop()
      if (activeThreadId === threadId) {
        setMessages([])
        setActiveThreadId(null)
      }
      await removeThread(threadId)
    },
    [activeThreadId, removeThread, stop, setMessages, setActiveThreadId],
  )

  const clear = useCallback(async () => {
    stop()
    setMessages([])
    setActiveThreadId(null)
    try { localStorage.removeItem(STREAMING_THREAD_KEY) } catch { /* ignore */ }
    try { await api.del("/api/v1/chat/history") } catch { /* best-effort */ }
  }, [stop, setMessages, setActiveThreadId])

  const continueChat = useCallback(() => {
    send("Continue your previous response from where you left off.")
  }, [send])

  const savePlan = useCallback(async () => {
    try {
      const res = await api.post<{ message: string }>("/api/v1/chat/save-plan", { history: messages })
      return res.message
    } catch (err) {
      const msg = `Failed to save: ${(err as Error).message}`
      toast.error(msg)
      return msg
    }
  }, [messages])

  return {
    messages, isStreaming, threads, activeThreadId,
    send, stop, clear, continueChat, savePlan,
    newChat, loadThread, renameThread, deleteThread,
  }
}
