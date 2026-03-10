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

  const refresh = useCallback(async (silent = false): Promise<TrackedFile[] | null> => {
    try {
      setError(null)
      const res = await api.get<PaginatedResponse<TrackedFile>>("/api/files")
      setFiles(res.items)
      return res.items
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      if (!silent) {
        toast.error(`Failed to load files: ${msg}`)
      }
      return null // null = error; empty array = success with no files
    }
  }, [])

  // Auto-poll while any file is being indexed
  useEffect(() => {
    const hasIndexing = files.some((f) => f.status === "indexing")
    if (hasIndexing && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        const updated = await refresh()
        if (!updated?.some((f: TrackedFile) => f.status === "indexing")) {
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

      // Only retry on actual errors (null), not empty results (fresh install)
      if (mounted && result === null && retryCount < MAX_RETRIES) {
        retryCount++
        retryTimer = setTimeout(loadWithRetry, 2000)
      }
    }

    loadWithRetry()

    return () => {
      mounted = false
      if (retryTimer) clearTimeout(retryTimer)
    }
  }, [refresh])

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

  const indexAll = useCallback(async () => {
    try {
      const res = await api.post<{ message: string }>("/api/index")
      toast.success(res.message)
      await refresh()
    } catch (err) {
      toast.error(`Failed to index: ${(err as Error).message}`)
    }
  }, [refresh])

  const unindexSource = useCallback(async (source: string) => {
    try {
      const res = await api.post<{ unindexed: number }>("/api/files/unindex-source", { source })
      toast.success(`Unindexed ${res.unindexed} files`)
      await refresh()
    } catch (err) {
      toast.error(`Failed to unindex: ${(err as Error).message}`)
    }
  }, [refresh])

  const updateTags = useCallback(async (path: string, tags: string[]) => {
    try {
      await api.put("/api/files/tags", { path, tags })
      await refresh()
    } catch (err) {
      toast.error(`Failed to update tags: ${(err as Error).message}`)
    }
  }, [refresh])

  const bulkUpdateTags = useCallback(async (paths: string[], tags: string[], mode: "add" | "remove" | "replace" = "add") => {
    try {
      const res = await api.put<{ updated: number }>("/api/files/bulk-tags", { paths, tags, mode })
      toast.success(`Updated tags on ${res.updated} files`)
      await refresh()
    } catch (err) {
      toast.error(`Failed to update tags: ${(err as Error).message}`)
    }
  }, [refresh])

  return { files, busyPaths, error, refresh, toggleRag, unindexFile, indexFile, reindexFile, indexAll, unindexSource, updateTags, bulkUpdateTags }
}
