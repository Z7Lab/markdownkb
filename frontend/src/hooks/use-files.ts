import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { TrackedFile } from "@/lib/types"

export function useFiles() {
  const [files, setFiles] = useState<TrackedFile[]>([])
  const [selectedFile, setSelectedFile] = useState<TrackedFile | null>(null)
  const [content, setContent] = useState("")
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    const res = await api.get<{ files: TrackedFile[] }>("/api/files")
    setFiles(res.files)
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const selectFile = useCallback(async (file: TrackedFile) => {
    setSelectedFile(file)
    try {
      const res = await api.get<{ content: string }>(
        `/api/file?path=${encodeURIComponent(file.path)}`,
      )
      setContent(res.content)
    } catch {
      setContent("Error loading file content.")
    }
  }, [])

  const [pendingExclude, setPendingExclude] = useState<TrackedFile | null>(null)

  const toggleRag = useCallback(async (file: TrackedFile, include: boolean) => {
    if (!include) {
      setPendingExclude(file)
      return
    }
    setLoading(true)
    try {
      await api.post("/api/files/include", { path: file.path })
      const res = await api.get<{ files: TrackedFile[] }>("/api/files")
      setFiles(res.files)
      const updated = res.files.find((f) => f.path === file.path)
      if (updated) setSelectedFile(updated)
    } finally {
      setLoading(false)
    }
  }, [])

  const confirmExclude = useCallback(async () => {
    if (!pendingExclude) return
    const file = pendingExclude
    setPendingExclude(null)
    setLoading(true)
    try {
      await api.post("/api/files/exclude", { path: file.path })
      const res = await api.get<{ files: TrackedFile[] }>("/api/files")
      setFiles(res.files)
      const updated = res.files.find((f) => f.path === file.path)
      if (updated) setSelectedFile(updated)
    } finally {
      setLoading(false)
    }
  }, [pendingExclude])

  return { files, selectedFile, content, loading, pendingExclude, refresh, selectFile, toggleRag, confirmExclude, setPendingExclude }
}
