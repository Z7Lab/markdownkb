import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import { parseFrontmatter } from "@/lib/utils"
import { toast } from "sonner"
import { copyToClipboard } from "@/lib/utils"

interface FileReadResponse {
  content: string
  page?: number
  total_pages?: number
  total_lines?: number
  page_size?: number
}

interface FileStatus {
  status: string
  include_rag: number
  chunk_count: number
}

const INITIAL_STATUS: FileStatus = { status: "not_indexed", include_rag: 1, chunk_count: 0 }

const PAGE_SIZE = 5000

export interface UseFileViewerReturn {
  rawContent: string
  loading: boolean
  actionLoading: boolean
  fileStatus: FileStatus
  editDialogOpen: boolean
  setEditDialogOpen: (open: boolean) => void
  pendingUnindex: boolean
  setPendingUnindex: (pending: boolean) => void
  page: number
  totalPages: number
  totalLines: number
  fileTags: string[]
  copyingAll: boolean
  fetchPage: (filePath: string, pageNum: number, signal?: AbortSignal) => Promise<void>
  handleSaveTags: (newTags: string[], createBackup: boolean, shouldReindex: boolean) => Promise<void>
  handleToggleRag: (checked: boolean) => Promise<void>
  handleIndexFile: () => Promise<void>
  handleReindexFile: () => Promise<void>
  handleUnindexFile: () => Promise<void>
  handleCopyContent: (isMarkdown: boolean) => Promise<void>
}

export function useFileViewer(path: string | null, bucketId?: string | null): UseFileViewerReturn {
  const [rawContent, setRawContent] = useState("")
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [fileStatus, setFileStatus] = useState<FileStatus>(INITIAL_STATUS)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [pendingUnindex, setPendingUnindex] = useState(false)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalLines, setTotalLines] = useState(0)
  const [fileTags, setFileTags] = useState<string[]>([])
  const [copyingAll, setCopyingAll] = useState(false)

  const fetchPage = useCallback(async (filePath: string, pageNum: number, signal?: AbortSignal) => {
    setLoading(true)
    try {
      let content: string
      let totalPagesVal = 1
      let totalLinesVal = 0
      let pageVal = pageNum

      if (bucketId) {
        const data = await api.get<{ path: string; title: string; content: string; chunk_count: number }>(
          `/api/v1/buckets/${bucketId}/file?path=${encodeURIComponent(filePath)}`,
          signal,
        )
        content = data.content
        totalLinesVal = content.split("\n").length
      } else {
        const res = await api.get<FileReadResponse>(
          `/api/v1/file?path=${encodeURIComponent(filePath)}&page=${pageNum}&page_size=${PAGE_SIZE}`,
          signal,
        )
        content = res.content
        pageVal = res.page ?? pageNum
        totalPagesVal = res.total_pages ?? 1
        totalLinesVal = res.total_lines ?? 0
      }

      if (signal?.aborted) return
      setRawContent(content)
      setPage(pageVal)
      setTotalPages(totalPagesVal)
      setTotalLines(totalLinesVal)
      if (pageNum === 1 && filePath.endsWith(".md")) {
        const { tags } = parseFrontmatter(content)
        setFileTags(tags)
      }
    } catch {
      if (signal?.aborted) return
      setRawContent("Error loading file.")
      setTotalPages(1)
      setTotalLines(0)
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [bucketId])

  useEffect(() => {
    if (!path) return
    setRawContent("")
    setPage(1)
    setTotalPages(1)
    setTotalLines(0)
    setFileTags([])

    const controller = new AbortController()

    fetchPage(path, 1, controller.signal)

    if (!bucketId) {
      api
        .get<{ path: string; status: string; include_rag: number; chunk_count: number }>(
          `/api/v1/file/status?path=${encodeURIComponent(path)}`,
          controller.signal,
        )
        .then((res) => {
          if (controller.signal.aborted) return
          setFileStatus({ status: res.status, include_rag: res.include_rag, chunk_count: res.chunk_count })
        })
        .catch(() => {
          if (controller.signal.aborted) return
          setFileStatus(INITIAL_STATUS)
        })
    }

    return () => controller.abort()
  }, [path, bucketId, fetchPage])

  const refreshFileStatus = async () => {
    if (!path) return
    const statusRes = await api.get<{ status: string; include_rag: number; chunk_count: number }>(
      `/api/v1/file/status?path=${encodeURIComponent(path)}`
    )
    setFileStatus({ status: statusRes.status, include_rag: statusRes.include_rag, chunk_count: statusRes.chunk_count })
  }

  const withAction = async (fn: () => Promise<void>) => {
    if (!path) return
    setActionLoading(true)
    try {
      await fn()
      await refreshFileStatus()
    } finally {
      setActionLoading(false)
    }
  }

  const handleSaveTags = async (newTags: string[], createBackup: boolean, shouldReindex: boolean) => {
    if (!path) return
    try {
      await api.put("/api/v1/files/tags", { path, tags: newTags })
      await fetchPage(path, 1)
      toast.success(createBackup ? "Tags updated! Backup created." : "Tags updated successfully!")
      if (shouldReindex) {
        try {
          await api.put("/api/v1/files/index", { path })
          toast.success("File reindexed successfully!")
          await refreshFileStatus()
        } catch (err) {
          toast.error(`Failed to reindex: ${(err as Error).message}`)
        }
      }
    } catch (err) {
      toast.error(`Failed to update tags: ${(err as Error).message}`)
      throw err
    }
  }

  const handleToggleRag = async (checked: boolean) => {
    await withAction(async () => {
      await api.put("/api/v1/files/rag", { path, include: checked })
      setFileStatus((prev) => ({ ...prev, include_rag: checked ? 1 : 0 }))
      toast.success(checked ? "File included in RAG" : "File excluded from RAG")
    })
  }

  const handleIndexFile = () => withAction(async () => {
    await api.post("/api/v1/files/index", { path })
    toast.success("File indexed successfully!")
  })

  const handleReindexFile = () => withAction(async () => {
    await api.put("/api/v1/files/index", { path })
    toast.success("File reindexed successfully!")
  })

  const handleUnindexFile = async () => {
    setPendingUnindex(false)
    await withAction(async () => {
      await api.del("/api/v1/files/index", { path })
      toast.success("File removed from index")
    })
  }

  const handleCopyContent = async (isMarkdown: boolean) => {
    if (!path) return
    setCopyingAll(true)
    try {
      let fullContent: string
      if (bucketId) {
        const data = await api.get<{ content: string }>(`/api/v1/buckets/${bucketId}/file?path=${encodeURIComponent(path)}`)
        fullContent = data.content
      } else {
        const res = await api.get<FileReadResponse>(`/api/v1/file?path=${encodeURIComponent(path)}`)
        fullContent = isMarkdown ? parseFrontmatter(res.content).content : res.content
      }
      const ok = await copyToClipboard(fullContent)
      if (ok) {
        toast.success("File content copied to clipboard")
      } else {
        toast.error("Failed to copy — clipboard access denied")
      }
    } catch {
      toast.error("Failed to load file content for copying")
    } finally {
      setCopyingAll(false)
    }
  }

  return {
    rawContent, loading, actionLoading, fileStatus,
    editDialogOpen, setEditDialogOpen,
    pendingUnindex, setPendingUnindex,
    page, totalPages, totalLines, fileTags, copyingAll,
    fetchPage, handleSaveTags, handleToggleRag,
    handleIndexFile, handleReindexFile, handleUnindexFile, handleCopyContent,
  }
}
