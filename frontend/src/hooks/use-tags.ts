import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { PaginatedResponse } from "@/lib/types"

export function useTags() {
  const [tags, setTags] = useState<string[]>([])

  const refresh = useCallback(async () => {
    try {
      const res = await api.get<PaginatedResponse<string>>("/api/v1/tags")
      setTags(res.items)
    } catch (err) {
      console.warn("Failed to load tags:", (err as Error).message)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { tags, refresh }
}
