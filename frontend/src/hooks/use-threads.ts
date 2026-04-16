import { useCallback, useEffect, useState } from "react"
import { api, retryWithBackoff } from "@/lib/api"
import { toast } from "sonner"
import type { PaginatedResponse, Thread } from "@/lib/types"

export function useThreads() {
  const [threads, setThreads] = useState<Thread[]>([])

  const refresh = useCallback(async (silent = false): Promise<boolean> => {
    try {
      const res = await api.get<PaginatedResponse<Thread>>("/api/v1/threads")
      setThreads(res.items)
      return true
    } catch (err) {
      if (!silent) {
        toast.error(`Failed to load threads: ${(err as Error).message}`)
      }
      return false
    }
  }, [])

  useEffect(() => {
    return retryWithBackoff(() => refresh(true))
  }, [refresh])

  const rename = useCallback(async (threadId: string, title: string) => {
    try {
      await api.patch(`/api/v1/threads/${threadId}`, { title })
      setThreads((prev) =>
        prev.map((t) => (t.id === threadId ? { ...t, title } : t)),
      )
    } catch (err) {
      toast.error(`Failed to rename thread: ${(err as Error).message}`)
    }
  }, [])

  const remove = useCallback(async (threadId: string) => {
    try {
      await api.del(`/api/v1/threads/${threadId}`)
      await refresh()
    } catch (err) {
      toast.error(`Failed to delete thread: ${(err as Error).message}`)
    }
  }, [refresh])

  const addOptimistic = useCallback((thread: Thread) => {
    setThreads((prev) => {
      if (prev.some((t) => t.id === thread.id)) return prev
      return [thread, ...prev]
    })
  }, [])

  return { threads, refreshThreads: refresh, renameThread: rename, deleteThread: remove, addOptimistic }
}
