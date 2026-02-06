import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { TrackedFile } from "@/lib/types"

export function useFiles() {
  const [files, setFiles] = useState<TrackedFile[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    const res = await api.get<{ files: TrackedFile[] }>("/api/files")
    setFiles(res.files)
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
    } finally {
      setLoading(false)
    }
  }, [pendingExclude, refresh])

  return { files, loading, pendingExclude, refresh, toggleRag, confirmExclude, setPendingExclude }
}
