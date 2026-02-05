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

  const toggleRag = useCallback(async (file: TrackedFile, include: boolean) => {
    setLoading(true)
    try {
      if (include) {
        await api.post("/api/files/include", { path: file.path })
      } else {
        await api.post("/api/files/exclude", { path: file.path })
      }
      await refresh()
    } finally {
      setLoading(false)
    }
  }, [refresh])

  return { files, selectedFile, content, loading, refresh, selectFile, toggleRag }
}
