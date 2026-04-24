import { useCallback, useEffect, useRef, useState } from "react"
import { streamChat } from "@/lib/sse"
import type { ChatMessage } from "@/lib/types"

let idCounter = 0
function nextId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID()
  return `msg-${Date.now()}-${++idCounter}`
}

export function useBucketChat(bucketId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const controllerRef = useRef<AbortController | null>(null)
  const threadIdRef = useRef<string | null>(null)
  const streamContentRef = useRef("")
  const flushTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

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

  useEffect(() => () => { cleanup() }, [cleanup])

  const send = useCallback((text: string) => {
    if (!text.trim() || isStreaming) return

    const userMsg: ChatMessage = { id: nextId(), role: "user", content: text }
    const assistantMsg: ChatMessage = { id: nextId(), role: "assistant", content: "" }
    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setIsStreaming(true)
    streamContentRef.current = ""
    flushTimerRef.current = setInterval(flushStreamContent, 33)

    controllerRef.current = streamChat(
      text,
      {
        onThread(threadId) { threadIdRef.current = threadId },
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
    )
  }, [isStreaming, bucketId, cleanup, flushStreamContent])

  const stop = useCallback(() => {
    controllerRef.current?.abort()
    cleanup()
  }, [cleanup])

  const clear = useCallback(() => {
    stop()
    threadIdRef.current = null
    setMessages([])
  }, [stop])

  return { messages, isStreaming, send, stop, clear }
}
