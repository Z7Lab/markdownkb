import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
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
}

export interface CreateBucketParams {
  name: string
  sources: { path: string; glob?: string }[]
  expires_in?: number | null
}

export function useBuckets() {
  const [buckets, setBuckets] = useState<Bucket[]>([])
  const [selectedBucketId, setSelectedBucketId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res = await api.get<{ buckets: Bucket[] }>("/api/buckets")
      setBuckets(res.buckets)
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
        const res = await api.post<Bucket>("/api/buckets", params)
        await refresh()
        toast.success(`Bucket "${res.name}" ready`, {
          id: toastId,
          description: `${res.file_count} file${res.file_count !== 1 ? "s" : ""}, ${res.chunk_count} chunk${res.chunk_count !== 1 ? "s" : ""}`,
          duration: 4000,
        })
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

  const deleteBucket = useCallback(
    async (id: string) => {
      const name = buckets.find((b) => b.id === id)?.name
      try {
        await api.del(`/api/buckets/${id}`)
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
      try {
        await api.patch(`/api/buckets/${id}`, { expires_in: expiresIn })
        await refresh()
        toast.success(expiresIn ? "Expiration updated" : "Bucket set to permanent", { duration: 2000 })
      } catch (err) {
        toast.error(`Failed to update: ${(err as Error).message}`)
      }
    },
    [refresh],
  )

  return {
    buckets,
    selectedBucketId,
    setSelectedBucketId,
    createBucket,
    deleteBucket,
    updateExpiration,
    refresh,
  }
}
