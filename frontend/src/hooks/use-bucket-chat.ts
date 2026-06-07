import { useCallback, useEffect, useRef, useState } from "react"
import { streamChat } from "@/lib/sse"
import { api } from "@/lib/api"
import { toast } from "sonner"
import type { ChatMessage, Thread } from "@/lib/types"

let idCounter = 0
function nextId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID()
  return `msg-${Date.now()}-${++idCounter}`
}

/**
 * Bucket-local chat. Conversations are persisted and owned by the bucket
 * (tagged `owner_bucket_id`), kept out of the global Chat tab, and surfaced
 * here as per-bucket history.
 */
export function useBucketChat(bucketId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)

  const controllerRef = useRef<AbortController | null>(null)
  const threadIdRef = useRef<string | null>(null)
  const streamContentRef = useRef("")
  const flushTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const loadIdRef = useRef(0)

  const refreshThreads = useCallback(async () => {
    try {
      const res = await api.get<{ items: Thread[] }>(`/api/v1/buckets/${bucketId}/threads`)
      setThreads(res.items)
    } catch {
      /* bucket may have no threads yet, or plugin disabled */
    }
  }, [bucketId])

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
  }, [])

  const cleanup = useCallback(() => {
    if (flushTimerRef.current) {
      clearInterval(flushTimerRef.current)
      flushTimerRef.current = null
    }
    flushStreamContent()
    streamContentRef.current = ""
    setIsStreaming(false)
    controllerRef.current = null
  }, [flushStreamContent])

  // Reset and reload history when the selected bucket changes.
  useEffect(() => {
    threadIdRef.current = null
    setActiveThreadId(null)
    setMessages([])
    refreshThreads()
    return () => { cleanup() }
  }, [bucketId, refreshThreads, cleanup])

  const send = useCallback((text: string) => {
    if (!text.trim() || isStreaming) return

    const isNewThread = threadIdRef.current === null
    const userMsg: ChatMessage = { id: nextId(), role: "user", content: text }
    const assistantMsg: ChatMessage = { id: nextId(), role: "assistant", content: "" }
    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setIsStreaming(true)
    streamContentRef.current = ""
    flushTimerRef.current = setInterval(flushStreamContent, 33)

    controllerRef.current = streamChat(
      text,
      {
        onThread(threadId) {
          threadIdRef.current = threadId
          setActiveThreadId(threadId)
          if (isNewThread) void refreshThreads()
        },
        onToken(content) { streamContentRef.current += content },
        onSources(sources, sourceMap) {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last?.role === "assistant") {
              updated[updated.length - 1] = { ...last, sources, ...(sourceMap ? { sourceMap } : {}) }
            }
            return updated
          })
        },
        onDone() { cleanup() },
        onError(error) {
          streamContentRef.current = `Error: ${error.message}`
          cleanup()
        },
      },
      threadIdRef.current,
      null,
      null,
      bucketId,
      null,
      isNewThread ? bucketId : null,
    )
  }, [isStreaming, bucketId, cleanup, flushStreamContent, refreshThreads])

  const stop = useCallback(() => {
    controllerRef.current?.abort()
    cleanup()
  }, [cleanup])

  const newChat = useCallback(() => {
    stop()
    threadIdRef.current = null
    setActiveThreadId(null)
    setMessages([])
  }, [stop])

  const loadThread = useCallback(async (threadId: string) => {
    stop()
    threadIdRef.current = threadId
    setActiveThreadId(threadId)
    const currentLoad = ++loadIdRef.current
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
      toast.error(`Failed to load conversation: ${(err as Error).message}`)
      setMessages([])
    }
  }, [stop])

  const deleteThread = useCallback(async (threadId: string) => {
    try {
      await api.del(`/api/v1/threads/${threadId}`)
      if (threadIdRef.current === threadId) {
        threadIdRef.current = null
        setActiveThreadId(null)
        setMessages([])
      }
      await refreshThreads()
    } catch (err) {
      toast.error(`Failed to delete conversation: ${(err as Error).message}`)
    }
  }, [refreshThreads])

  const activeTitle = threads.find((t) => t.id === activeThreadId)?.title ?? null

  return {
    messages, isStreaming, send, stop,
    threads, activeThreadId, activeTitle,
    newChat, loadThread, deleteThread, refreshThreads,
  }
}
