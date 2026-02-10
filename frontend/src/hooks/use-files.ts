import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import type { PaginatedResponse, TrackedFile } from "@/lib/types"

export function useFiles() {
  const [files, setFiles] = useState<TrackedFile[]>([])
  const [busyPaths, setBusyPaths] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const addBusy = (path: string) =>
    setBusyPaths((prev) => new Set([...prev, path]))
  const removeBusy = (path: string) =>
    setBusyPaths((prev) => {
      const next = new Set(prev)
      next.delete(path)
      return next
    })

  const refresh = useCallback(async (silent = false) => {
    try {
      setError(null)
      const res = await api.get<PaginatedResponse<TrackedFile>>("/api/files?limit=500")
      setFiles(res.items)
      return res.items
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      // Only show toast if not silent (i.e., not on initial/retry loads)
      if (!silent) {
        toast.error(`Failed to load files: ${msg}`)
      }
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

  // Initial load with retry on failure
  useEffect(() => {
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let mounted = true
    let retryCount = 0
    const MAX_RETRIES = 10

    const loadWithRetry = async () => {
      const result = await refresh(true) // silent = true

      // If load failed (empty result) and haven't exceeded max retries, retry in 2 seconds
      if (mounted && result.length === 0 && retryCount < MAX_RETRIES) {
        retryCount++
        retryTimer = setTimeout(loadWithRetry, 2000)
      }
    }

    loadWithRetry()

    return () => {
      mounted = false
      if (retryTimer) clearTimeout(retryTimer)
    }
    // Only run on mount - deliberately excluding dependencies to prevent retry loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run on mount

  const toggleRag = useCallback(async (path: string, include: boolean) => {
    addBusy(path)
    try {
      await api.put("/api/files/toggle-rag", { path, include })
      await refresh()
    } catch (err) {
      toast.error(`Failed to toggle RAG: ${(err as Error).message}`)
    } finally {
      removeBusy(path)
    }
  }, [refresh])

  const unindexFile = useCallback(async (path: string) => {
    addBusy(path)
    try {
      await api.post("/api/files/unindex", { path })
      await refresh()
    } catch (err) {
      toast.error(`Failed to unindex: ${(err as Error).message}`)
    } finally {
      removeBusy(path)
    }
  }, [refresh])

  const indexFile = useCallback(async (path: string) => {
    addBusy(path)
    setFiles((prev) => prev.map((f) => f.path === path ? { ...f, status: "indexing" } : f))
    try {
      await api.post("/api/files/index", { path })
      await refresh()
    } catch (err) {
      toast.error(`Failed to index: ${(err as Error).message}`)
      await refresh()
    } finally {
      removeBusy(path)
    }
  }, [refresh])

  const reindexFile = useCallback(async (path: string) => {
    addBusy(path)
    setFiles((prev) => prev.map((f) => f.path === path ? { ...f, status: "indexing" } : f))
    try {
      await api.post("/api/files/reindex", { path })
      await refresh()
    } catch (err) {
      toast.error(`Failed to reindex: ${(err as Error).message}`)
      await refresh()
    } finally {
      removeBusy(path)
    }
  }, [refresh])

  return { files, busyPaths, error, refresh, toggleRag, unindexFile, indexFile, reindexFile }
}
