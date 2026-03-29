import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react"
import { parseSSEStream } from "@/lib/sse"
import { toast } from "sonner"

export interface IndexEvent {
  type: "indexed" | "deleted" | "error" | "indexing"
  path: string
  filename: string
  chunks: number
  error: string
  ts: number
}

const INDEX_EVENT_TYPES = new Set(["indexed", "deleted", "error", "indexing"])

function isIndexEvent(data: unknown): data is IndexEvent {
  if (typeof data !== "object" || data === null) return false
  const obj = data as Record<string, unknown>
  return typeof obj.type === "string" && INDEX_EVENT_TYPES.has(obj.type) && typeof obj.path === "string"
}

interface IndexEventState {
  /** True when any file is currently being indexed */
  isIndexing: boolean
  /** Count of files with errors since last clear */
  errorCount: number
  /** Timestamp of last completed index event (for staleness checks) */
  lastIndexedAt: number | null
  /** Clear the error count */
  clearErrors: () => void
}

const IndexEventContext = createContext<IndexEventState>({
  isIndexing: false,
  errorCount: 0,
  lastIndexedAt: null,
  clearErrors: () => {},
})

// Co-located with IndexEventProvider for cohesion — splitting into separate files
// would add indirection without benefit since the hook is tightly coupled to the provider.
// eslint-disable-next-line react-refresh/only-export-components
export function useIndexEvents() {
  return useContext(IndexEventContext)
}

export function IndexEventProvider({ children }: { children: ReactNode }) {
  const [isIndexing, setIsIndexing] = useState(false)
  const [errorCount, setErrorCount] = useState(0)
  const [lastIndexedAt, setLastIndexedAt] = useState<number | null>(null)
  const indexingFiles = useRef(new Set<string>())
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearErrors = useCallback(() => setErrorCount(0), [])

  const handleEvent = useCallback((event: IndexEvent) => {
    switch (event.type) {
      case "indexing":
        indexingFiles.current.add(event.path)
        setIsIndexing(true)
        break

      case "indexed":
        indexingFiles.current.delete(event.path)
        setIsIndexing(indexingFiles.current.size > 0)
        setLastIndexedAt(event.ts)
        toast.success(`Indexed: ${event.filename}`, {
          description: `${event.chunks} chunk${event.chunks !== 1 ? "s" : ""}`,
          duration: 3000,
        })
        break

      case "deleted":
        indexingFiles.current.delete(event.path)
        setIsIndexing(indexingFiles.current.size > 0)
        setLastIndexedAt(event.ts)
        toast.info(`Removed: ${event.filename}`, { duration: 3000 })
        break

      case "error":
        indexingFiles.current.delete(event.path)
        setIsIndexing(indexingFiles.current.size > 0)
        setErrorCount((c) => c + 1)
        toast.error(`Index error: ${event.filename}`, {
          description: event.error,
          duration: 5000,
        })
        break
    }
  }, [])

  useEffect(() => {
    let controller: AbortController | null = null
    let mounted = true

    async function connect() {
      if (!mounted) return
      controller = new AbortController()

      try {
        const res = await fetch("/api/index/events", {
          signal: controller.signal,
        })
        if (!res.ok || !res.body) return

        const reader = res.body.getReader()
        await parseSSEStream(reader, (eventType, data) => {
          if (eventType === "index" && isIndexEvent(data)) {
            handleEvent(data)
          }
        })
      } catch {
        // Connection lost — retry after a delay
      }

      // Auto-reconnect
      if (mounted) {
        retryTimer.current = setTimeout(connect, 5000)
      }
    }

    connect()

    return () => {
      mounted = false
      controller?.abort()
      if (retryTimer.current) clearTimeout(retryTimer.current)
    }
  }, [handleEvent])

  return (
    <IndexEventContext value={{
      isIndexing,
      errorCount,
      lastIndexedAt,
      clearErrors,
    }}>
      {children}
    </IndexEventContext>
  )
}
