import { useCallback, useEffect, useState } from "react"
import { api } from "@/lib/api"
import type { SearchResult } from "@/lib/types"

export function useSearch() {
  const [query, setQuery] = useState("")
  const [folder, setFolder] = useState<string | null>(null)
  const [tag, setTag] = useState<string | null>(null)
  const [results, setResults] = useState<SearchResult[]>([])
  const [folders, setFolders] = useState<string[]>([])
  const [tags, setTags] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.get<{ folders: string[] }>("/api/folders").then((r) => setFolders(r.folders))
    api.get<{ tags: string[] }>("/api/tags").then((r) => setTags(r.tags))
  }, [])

  const search = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await api.post<{ results: SearchResult[] }>("/api/search", {
        query: query.trim(),
        folder: folder || undefined,
        tag: tag || undefined,
      })
      setResults(res.results)
    } finally {
      setLoading(false)
    }
  }, [query, folder, tag])

  return { query, setQuery, folder, setFolder, tag, setTag, results, folders, tags, loading, search }
}
