import { useCallback, useEffect, useMemo, useState } from "react"

const STORAGE_KEY_SCOPES = "markdownkb-scope-ids"
const STORAGE_KEY_TAGS = "markdownkb-ad-hoc-tags"
const STORAGE_KEY_BUCKETS = "markdownkb-bucket-ids"

/** Read a Set<string> from localStorage */
function loadSet(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(key)
    if (raw) {
      const arr = JSON.parse(raw)
      if (Array.isArray(arr)) return new Set(arr)
    }
  } catch { /* ignore */ }
  return new Set()
}

/** Persist a Set<string> to localStorage */
function saveSet(key: string, set: Set<string>) {
  try {
    localStorage.setItem(key, JSON.stringify(Array.from(set)))
  } catch { /* ignore */ }
}

/**
 * Shared hook for scope, ad-hoc tag, and bucket filter state.
 *
 * Persisted to localStorage so the filter survives tab switches
 * and page refreshes. All tabs (Chat, Search, Planner, Doc Map)
 * share the same filter state.
 */
export function useScopeTagFilter() {
  const [selectedScopeIds, setSelectedScopeIdsRaw] = useState<Set<string>>(() => loadSet(STORAGE_KEY_SCOPES))
  const [selectedTags, setSelectedTagsRaw] = useState<Set<string>>(() => loadSet(STORAGE_KEY_TAGS))
  const [selectedBucketIds, setSelectedBucketIdsRaw] = useState<Set<string>>(() => loadSet(STORAGE_KEY_BUCKETS))

  // Persist on change
  const setSelectedScopeIds = useCallback((value: Set<string> | ((prev: Set<string>) => Set<string>)) => {
    setSelectedScopeIdsRaw((prev) => {
      const next = typeof value === "function" ? value(prev) : value
      saveSet(STORAGE_KEY_SCOPES, next)
      return next
    })
  }, [])

  const setSelectedTags = useCallback((value: Set<string> | ((prev: Set<string>) => Set<string>)) => {
    setSelectedTagsRaw((prev) => {
      const next = typeof value === "function" ? value(prev) : value
      saveSet(STORAGE_KEY_TAGS, next)
      return next
    })
  }, [])

  const setSelectedBucketIds = useCallback((value: Set<string> | ((prev: Set<string>) => Set<string>)) => {
    setSelectedBucketIdsRaw((prev) => {
      const next = typeof value === "function" ? value(prev) : value
      saveSet(STORAGE_KEY_BUCKETS, next)
      return next
    })
  }, [])

  // Listen for storage events from other tabs (same browser)
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === STORAGE_KEY_SCOPES) setSelectedScopeIdsRaw(loadSet(STORAGE_KEY_SCOPES))
      if (e.key === STORAGE_KEY_TAGS) setSelectedTagsRaw(loadSet(STORAGE_KEY_TAGS))
      if (e.key === STORAGE_KEY_BUCKETS) setSelectedBucketIdsRaw(loadSet(STORAGE_KEY_BUCKETS))
    }
    window.addEventListener("storage", onStorage)
    return () => window.removeEventListener("storage", onStorage)
  }, [])

  const bucketIdsParam = useMemo(() => {
    if (selectedBucketIds.size === 0) return null
    return Array.from(selectedBucketIds).sort().join(",")
  }, [selectedBucketIds])

  const scopeIdsParam = useMemo(() => {
    if (selectedScopeIds.size === 0) return null
    return Array.from(selectedScopeIds).sort().join(",")
  }, [selectedScopeIds])

  const adHocTagsParam = useMemo(() => {
    if (selectedTags.size === 0) return null
    return Array.from(selectedTags).sort()
  }, [selectedTags])

  return {
    selectedScopeIds,
    selectedTags,
    selectedBucketIds,
    scopeIdsParam,
    bucketIdsParam,
    adHocTagsParam,
    handleScopeChange: setSelectedScopeIds,
    handleTagChange: setSelectedTags,
    handleBucketChange: setSelectedBucketIds,
  }
}
