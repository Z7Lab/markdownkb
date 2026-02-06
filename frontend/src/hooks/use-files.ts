import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"
import type { PaginatedResponse, TrackedFile } from "@/lib/types"

export function useFiles() {
  const [files, setFiles] = useState<TrackedFile[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setError(null)
      const res = await api.get<PaginatedResponse<TrackedFile>>("/api/files")
      setFiles(res.items)
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Failed to load files: ${msg}`)
    }
  }, [])

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
