import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"

export interface Bucket {
  id: string
  name: string
  sources: string
  file_count: number
  chunk_count: number
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
      try {
        const res = await api.post<Bucket>("/api/buckets", params)
        await refresh()
        return res
      } catch (err) {
        toast.error(`Failed to create bucket: ${(err as Error).message}`)
        return null
      }
    },
    [refresh],
  )

  const deleteBucket = useCallback(
    async (id: string) => {
      try {
        await api.del(`/api/buckets/${id}`)
        if (selectedBucketId === id) setSelectedBucketId(null)
        await refresh()
        return true
      } catch (err) {
        toast.error(`Failed to delete bucket: ${(err as Error).message}`)
        return false
      }
    },
    [refresh, selectedBucketId],
  )

  return {
    buckets,
    selectedBucketId,
    setSelectedBucketId,
    createBucket,
    deleteBucket,
    refresh,
  }
}
