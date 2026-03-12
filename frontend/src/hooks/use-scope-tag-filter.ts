import { useCallback, useMemo, useState } from "react"

/**
 * Shared hook for scope and ad-hoc tag filter state.
 * Used by chat-tab, search-tab, and graph-tab to avoid duplicating
 * the selectedScopeIds / selectedTags / param-derivation pattern.
 */
export function useScopeTagFilter() {
  const [selectedScopeIds, setSelectedScopeIds] = useState<Set<string>>(new Set())
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set())

  const scopeIdsParam = useMemo(() => {
    if (selectedScopeIds.size === 0) return null
    return Array.from(selectedScopeIds).sort().join(",")
  }, [selectedScopeIds])

  const adHocTagsParam = useMemo(() => {
    if (selectedTags.size === 0) return null
    return Array.from(selectedTags).sort()
  }, [selectedTags])

  const handleScopeChange = useCallback((ids: Set<string>) => {
    setSelectedScopeIds(ids)
  }, [])

  const handleTagChange = useCallback((tags: Set<string>) => {
    setSelectedTags(tags)
  }, [])

  return {
    selectedScopeIds,
    selectedTags,
    scopeIdsParam,
    adHocTagsParam,
    handleScopeChange,
    handleTagChange,
  }
}
