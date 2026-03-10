import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { PaginatedResponse } from "@/lib/types"

export function useTags() {
  const [tags, setTags] = useState<string[]>([])

  const refresh = useCallback(async () => {
    try {
      const res = await api.get<PaginatedResponse<string>>("/api/tags")
      setTags(res.items)
    } catch {
      // Tags are optional
    }
  }, [])

  useEffect(() => {
    refresh() // eslint-disable-line react-hooks/set-state-in-effect -- initial data fetch on mount
  }, [refresh])

  return { tags, refresh }
}
