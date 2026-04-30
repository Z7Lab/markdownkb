import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import { setVisibilityInterval } from "@/lib/polling"
import { toast } from "sonner"

export interface Bucket {
  id: string
  name: string
  sources: string
  file_count: number
  chunk_count: number
  indexed_chunks?: number
  indexing?: boolean
  created_at: string
  expires_at: string | null
  expired: boolean
  color: string | null
  description: string | null
  scope_paths: string[] | null
}

export interface CreateBucketParams {
  name: string
  sources: { path: string; glob?: string }[]
  expires_in?: number | null
  color?: string | null
  description?: string | null
}

export interface UpdateBucketParams {
  name?: string
  expires_in?: number | null
  color?: string | null
  description?: string | null
  scope_paths?: string[] | null
}

export interface BucketFile {
  path: string
  title: string
  chunk_count: number
  indexed_at: string | null
}

export function useBucketFiles(bucketId: string | null) {
  const [files, setFiles] = useState<BucketFile[]>([])
  const [loading, setLoading] = useState(false)
  const [indexing, setIndexing] = useState(false)

  const load = useCallback(async () => {
    if (!bucketId) return
    setLoading(true)
    try {
      const res = await api.get<{ files: BucketFile[]; indexing?: boolean }>(`/api/v1/buckets/${bucketId}/files`)
      setFiles(res.files)
      setIndexing(res.indexing ?? false)
    } catch (err) {
      console.error("Failed to load bucket files", err)
    } finally {
      setLoading(false)
    }
  }, [bucketId])

  useEffect(() => {
    if (bucketId) {
      load()
    } else {
      setFiles([])
      setIndexing(false)
    }
  }, [bucketId, load])

  // Poll while embedding is in progress so files get their chunk counts once done
  useEffect(() => {
    if (!indexing) return
    return setVisibilityInterval(() => {
      void load()
    }, 3000)
  }, [indexing, load])

  return { files, loading, indexing, reload: load }
}

export function useBuckets() {
  const [buckets, setBuckets] = useState<Bucket[]>([])
  const [selectedBucketId, setSelectedBucketId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res = await api.get<{ buckets: Bucket[] }>("/api/v1/buckets")
      // SQLite returns expired as 0/1 integer; coerce to boolean at the boundary
      setBuckets(res.buckets.map((b) => ({ ...b, expired: Boolean(b.expired) })))
    } catch {
      // Buckets plugin may be disabled
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const createBucket = useCallback(
    async (params: CreateBucketParams) => {
      const toastId = toast.loading(`Creating bucket "${params.name}"...`, {
        description: "Scanning, chunking, and embedding documents",
      })
      try {
        const res = await api.post<Bucket & { docker_restart_required?: boolean }>("/api/v1/buckets", params)
        await refresh()
        if (res.docker_restart_required) {
          toast.success(`Bucket "${res.name}" created`, {
            id: toastId,
            description: "Docker restart required to mount the new path.",
            duration: 4000,
          })
        } else {
          toast.success(`Bucket "${res.name}" ready`, {
            id: toastId,
            description: `${res.file_count} file${res.file_count !== 1 ? "s" : ""}, ${res.chunk_count} chunk${res.chunk_count !== 1 ? "s" : ""}`,
            duration: 4000,
          })
        }
        return res
      } catch (err) {
        toast.error(`Failed to create bucket: ${(err as Error).message}`, {
          id: toastId,
        })
        return null
      }
    },
    [refresh],
  )

  const updateBucket = useCallback(
    async (id: string, params: UpdateBucketParams) => {
      try {
        await api.patch(`/api/v1/buckets/${id}`, params)
        await refresh()
        toast.success("Bucket updated", { duration: 2000 })
      } catch (err) {
        toast.error(`Failed to update: ${(err as Error).message}`)
      }
    },
    [refresh],
  )

  const deleteBucket = useCallback(
    async (id: string) => {
      const name = buckets.find((b) => b.id === id)?.name
      try {
        await api.del(`/api/v1/buckets/${id}`)
        if (selectedBucketId === id) setSelectedBucketId(null)
        await refresh()
        toast.success(`Bucket "${name ?? id}" deleted`, { duration: 3000 })
        return true
      } catch (err) {
        toast.error(`Failed to delete bucket: ${(err as Error).message}`)
        return false
      }
    },
    [buckets, refresh, selectedBucketId],
  )

  const updateExpiration = useCallback(
    async (id: string, expiresIn: number | null) => {
      await updateBucket(id, { expires_in: expiresIn })
    },
    [updateBucket],
  )

  const exportBucket = useCallback((id: string, name: string) => {
    const toastId = toast.loading(`Exporting "${name}"...`)
    api
      .fetchRaw("GET", `/api/v1/buckets/${id}/export`)
      .then(async (res) => {
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = `bucket-${name}.zip`
        a.click()
        URL.revokeObjectURL(url)
        toast.success(`Exported "${name}"`, { id: toastId, duration: 3000 })
      })
      .catch((err: unknown) => {
        toast.error(`Export failed: ${(err as Error).message}`, { id: toastId })
      })
  }, [])

  const importBucket = useCallback(
    async (file: File): Promise<Bucket | null> => {
      const toastId = toast.loading(`Importing "${file.name}"...`)
      try {
        const fd = new FormData()
        fd.append("file", file)
        const bucket = await api.upload<Bucket>("/api/v1/buckets/import", fd)
        await refresh()
        toast.success(`Imported bucket "${bucket.name}"`, {
          id: toastId,
          description: `${bucket.chunk_count} chunks`,
          duration: 4000,
        })
        return bucket
      } catch (err) {
        toast.error(`Import failed: ${(err as Error).message}`, { id: toastId })
        return null
      }
    },
    [refresh],
  )

  const promoteBucket = useCallback(async (id: string, name: string) => {
    const toastId = toast.loading(`Promoting "${name}" to watched directories...`)
    try {
      const res = await api.post<{ promoted: string[]; already_present: string[]; message: string }>(
        `/api/v1/buckets/${id}/promote`,
        {},
      )
      toast.success(`Promoted "${name}"`, {
        id: toastId,
        description: res.message,
        duration: 5000,
      })
      return res
    } catch (err) {
      toast.error(`Promote failed: ${(err as Error).message}`, { id: toastId })
      return null
    }
  }, [])

  return {
    buckets,
    selectedBucketId,
    setSelectedBucketId,
    createBucket,
    updateBucket,
    deleteBucket,
    updateExpiration,
    exportBucket,
    importBucket,
    promoteBucket,
    refresh,
  }
}
