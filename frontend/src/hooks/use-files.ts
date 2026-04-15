import { useCallback, useEffect, useRef, useState } from "react"
import { api, retryWithBackoff } from "@/lib/api"
import { toast } from "sonner"
import type { PaginatedResponse, TrackedFile } from "@/lib/types"

export function useFiles() {
  const [files, setFiles] = useState<TrackedFile[]>([])
  const [busyPaths, setBusyPaths] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const addBusy = useCallback((path: string) =>
    setBusyPaths((prev) => {
      if (prev.has(path)) return prev
      const next = new Set(prev)
      next.add(path)
      return next
    }), [])
  const removeBusy = useCallback((path: string) =>
    setBusyPaths((prev) => {
      if (!prev.has(path)) return prev
      const next = new Set(prev)
      next.delete(path)
      return next
    }), [])

  const refresh = useCallback(async (silent = false): Promise<TrackedFile[] | null> => {
    try {
      setError(null)
      const [res, entityRes] = await Promise.all([
        api.get<PaginatedResponse<TrackedFile>>("/api/v1/files"),
        api.get<{ counts: Record<string, number> }>("/api/v1/knowledge-graph/file-entity-counts").catch(() => null),
      ])
      const counts = entityRes?.counts ?? {}
      const items = res.items.map((f) => ({
        ...f,
        entity_count: counts[f.path] ?? undefined,
      }))
      setFiles(items)
      return items
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      if (!silent) {
        toast.error(`Failed to load files: ${msg}`)
      }
      return null // null = error; empty array = success with no files
    }
  }, [])

  // Derive a boolean so the poll effect only re-runs when indexing state flips
  const hasIndexing = files.some((f) => f.status === "indexing")

  // Auto-poll while any file is being indexed
  useEffect(() => {
    if (!hasIndexing) {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      return
    }
    if (pollRef.current) return // already polling
    pollRef.current = setInterval(async () => {
      const updated = await refresh()
      if (!updated?.some((f: TrackedFile) => f.status === "indexing")) {
        if (pollRef.current) clearInterval(pollRef.current)
        pollRef.current = null
      }
    }, 3000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [hasIndexing, refresh])

  // Initial load with retry on failure
  useEffect(() => {
    return retryWithBackoff(async () => {
      const result = await refresh(true)
      return result !== null // null = error, retry; array = success
    })
  }, [refresh])

  const toggleRag = useCallback(async (path: string, include: boolean) => {
    addBusy(path)
    try {
      await api.put("/api/v1/files/rag", { path, include })
      await refresh()
    } catch (err) {
      toast.error(`Failed to toggle RAG: ${(err as Error).message}`)
    } finally {
      removeBusy(path)
    }
  }, [refresh, addBusy, removeBusy])

  const unindexFile = useCallback(async (path: string) => {
    addBusy(path)
    try {
      await api.del("/api/v1/files/index", { path })
      await refresh()
    } catch (err) {
      toast.error(`Failed to unindex: ${(err as Error).message}`)
    } finally {
      removeBusy(path)
    }
  }, [refresh, addBusy, removeBusy])

  const indexFile = useCallback(async (path: string) => {
    addBusy(path)
    setFiles((prev) => prev.map((f) => f.path === path ? { ...f, status: "indexing" } : f))
    try {
      await api.post("/api/v1/files/index", { path })
      await refresh()
    } catch (err) {
      toast.error(`Failed to index: ${(err as Error).message}`)
      await refresh()
    } finally {
      removeBusy(path)
    }
  }, [refresh, addBusy, removeBusy])

  const reindexFile = useCallback(async (path: string) => {
    addBusy(path)
    setFiles((prev) => prev.map((f) => f.path === path ? { ...f, status: "indexing" } : f))
    try {
      await api.put("/api/v1/files/index", { path })
      await refresh()
    } catch (err) {
      toast.error(`Failed to reindex: ${(err as Error).message}`)
      await refresh()
    } finally {
      removeBusy(path)
    }
  }, [refresh, addBusy, removeBusy])

  const indexAll = useCallback(async () => {
    try {
      const res = await api.post<{ message: string }>("/api/v1/index")
      toast.success(res.message)
      await refresh()
    } catch (err) {
      toast.error(`Failed to index: ${(err as Error).message}`)
    }
  }, [refresh])

  const unindexSource = useCallback(async (source: string) => {
    try {
      const res = await api.del<{ unindexed: number }>("/api/v1/sources/index", { source })
      toast.success(`Unindexed ${res.unindexed} files`)
      await refresh()
    } catch (err) {
      toast.error(`Failed to unindex: ${(err as Error).message}`)
    }
  }, [refresh])

  const updateTags = useCallback(async (path: string, tags: string[]) => {
    try {
      await api.put("/api/v1/files/tags", { path, tags })
      await refresh()
    } catch (err) {
      toast.error(`Failed to update tags: ${(err as Error).message}`)
    }
  }, [refresh])

  const bulkUpdateTags = useCallback(async (paths: string[], tags: string[], mode: "add" | "remove" | "replace" = "add") => {
    try {
      const res = await api.put<{ updated: number }>("/api/v1/files/bulk-tags", { paths, tags, mode })
      toast.success(`Updated tags on ${res.updated} files`)
      await refresh()
    } catch (err) {
      toast.error(`Failed to update tags: ${(err as Error).message}`)
    }
  }, [refresh])

  const extractEntities = useCallback(async (path: string) => {
    addBusy(path)
    try {
      const res = await api.post<{ entities: number }>(`/api/v1/knowledge-graph/extract-file?path=${encodeURIComponent(path)}`)
      toast.success(`Extracted ${res.entities} entities from ${path.split("/").pop()}`)
      await refresh()
    } catch (err) {
      toast.error(`Failed to extract entities: ${(err as Error).message}`)
    } finally {
      removeBusy(path)
    }
  }, [refresh, addBusy, removeBusy])

  return { files, busyPaths, error, refresh, toggleRag, unindexFile, indexFile, reindexFile, indexAll, unindexSource, updateTags, bulkUpdateTags, extractEntities }
}
