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

  const toggleRag = useCallback(async (path: string, include: boolean) => {
    setLoading(true)
    try {
      await api.put("/api/files/toggle-rag", { path, include })
      await refresh()
    } catch (err) {
      toast.error(`Failed to toggle RAG: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }, [refresh])

  const unindexFile = useCallback(async (path: string) => {
    setLoading(true)
    try {
      await api.post("/api/files/unindex", { path })
      await refresh()
    } catch (err) {
      toast.error(`Failed to unindex: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }, [refresh])

  const indexFile = useCallback(async (path: string) => {
    setLoading(true)
    try {
      await api.post("/api/files/index", { path })
      await refresh()
    } catch (err) {
      toast.error(`Failed to index: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }, [refresh])

  const reindexFile = useCallback(async (path: string) => {
    setLoading(true)
    try {
      await api.post("/api/files/reindex", { path })
      await refresh()
    } catch (err) {
      toast.error(`Failed to reindex: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }, [refresh])

  return { files, loading, error, refresh, toggleRag, unindexFile, indexFile, reindexFile }
}
