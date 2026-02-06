import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import type { PaginatedResponse, TrackedFile } from "@/lib/types"

export function useFiles() {
  const [files, setFiles] = useState<TrackedFile[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refresh = useCallback(async () => {
    try {
      setError(null)
      const res = await api.get<PaginatedResponse<TrackedFile>>("/api/files?limit=500")
      setFiles(res.items)
      return res.items
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Failed to load files: ${msg}`)
      return []
    }
  }, [])

  // Auto-poll while any file is being indexed
  useEffect(() => {
    const hasIndexing = files.some((f) => f.status === "indexing")
    if (hasIndexing && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        const updated = await refresh()
        if (!updated.some((f: TrackedFile) => f.status === "indexing")) {
          if (pollRef.current) clearInterval(pollRef.current)
          pollRef.current = null
        }
      }, 3000)
    }
    if (!hasIndexing && pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [files, refresh])

  useEffect(() => {
    refresh()
  }, [refresh])

  const [pendingExclude, setPendingExclude] = useState<TrackedFile | null>(null)

  const toggleRag = useCallback(async (file: TrackedFile, include: boolean) => {
    if (!include) {
      setPendingExclude(file)
      return
    }
    setLoading(true)
    try {
      await api.post("/api/files/include", { path: file.path })
      await refresh()
    } catch (err) {
      toast.error(`Failed to include file: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }, [refresh])

  const confirmExclude = useCallback(async () => {
    if (!pendingExclude) return
    setPendingExclude(null)
    setLoading(true)
    try {
      await api.post("/api/files/exclude", { path: pendingExclude.path })
      await refresh()
    } catch (err) {
      toast.error(`Failed to exclude file: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }, [pendingExclude, refresh])

  return { files, loading, error, pendingExclude, refresh, toggleRag, confirmExclude, setPendingExclude }
}
