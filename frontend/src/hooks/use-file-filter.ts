import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { basename, dirname } from "@/lib/utils"
import type { TrackedFile } from "@/lib/types"

/** Multi-term AND: split on spaces, each term must substring-match in the path */
function filterMatch(text: string, pattern: string): boolean {
  const textLower = text.toLowerCase()
  const terms = pattern.toLowerCase().split(/\s+/).filter(Boolean)
  return terms.every((term) => textLower.includes(term))
}

function useContentSearch(filterText: string, searchMode: "path" | "content") {
  const [contentMatches, setContentMatches] = useState<Set<string> | null>(null)
  const [contentSearching, setContentSearching] = useState(false)
  const contentDebounce = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (searchMode !== "content" || !filterText.trim()) {
      setContentMatches(null)
      return
    }
    if (contentDebounce.current) clearTimeout(contentDebounce.current)
    setContentSearching(true)
    contentDebounce.current = setTimeout(async () => {
      try {
        const res = await api.post<{ paths: string[] }>("/api/v1/files/search", {
          query: filterText,
          top_k: 50,
        })
        setContentMatches(new Set(res.paths))
      } catch (err) {
        console.warn("Content search failed:", (err as Error).message)
        setContentMatches(new Set<string>())
      } finally {
        setContentSearching(false)
      }
    }, 400)
    return () => { if (contentDebounce.current) clearTimeout(contentDebounce.current) }
  }, [filterText, searchMode])

  const clearMatches = useCallback(() => setContentMatches(null), [])

  return { contentMatches, contentSearching, clearMatches }
}

export const getValue = (f: TrackedFile, key: string): string | number | null => {
  switch (key) {
    case "file": return basename(f.path)
    case "folder": return dirname(f.path)
    case "tags": return f.tags || ""
    case "include": return f.include_in_index
    case "status": return f.status
    case "chunks": return f.chunk_count
    case "entities": return f.entity_count ?? 0
    case "indexed": return f.indexed_at || ""
    default: return null
  }
}

export interface UseFileFilterReturn {
  filterText: string
  setFilterText: (text: string) => void
  searchMode: "path" | "content"
  setSearchMode: (mode: "path" | "content") => void
  contentSearching: boolean
  clearMatches: () => void
  /** Files after folder selection (before text filter) — used for count display */
  folderFiltered: TrackedFile[]
  filteredFiles: TrackedFile[]
}

export function useFileFilter(
  sorted: TrackedFile[],
  selectedFolder: string | null,
): UseFileFilterReturn {
  const [filterText, setFilterText] = useState("")
  const [searchMode, setSearchMode] = useState<"path" | "content">("path")
  const { contentMatches, contentSearching, clearMatches } = useContentSearch(filterText, searchMode)

  const folderFiltered = selectedFolder
    ? sorted.filter((f) => {
        const dir = dirname(f.path)
        return dir === selectedFolder || dir.startsWith(selectedFolder + "/")
      })
    : sorted

  const filteredFiles = filterText
    ? searchMode === "content"
      ? contentMatches
        ? folderFiltered.filter((f) => contentMatches.has(f.path))
        : contentSearching ? [] : folderFiltered
      : folderFiltered.filter((f) => filterMatch(f.path, filterText))
    : folderFiltered

  return {
    filterText, setFilterText,
    searchMode, setSearchMode,
    contentSearching, clearMatches,
    folderFiltered,
    filteredFiles,
  }
}
