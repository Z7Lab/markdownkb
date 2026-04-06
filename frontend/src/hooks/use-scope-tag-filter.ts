import { useMemo, useState } from "react"

/**
 * Shared hook for scope, ad-hoc tag, and bucket filter state.
 * Used by chat-tab, search-tab, and visualization-tab to avoid duplicating
 * the selectedScopeIds / selectedTags / param-derivation pattern.
 */
export function useScopeTagFilter() {
  const [selectedScopeIds, setSelectedScopeIds] = useState<Set<string>>(new Set())
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set())
  const [selectedBucketId, setSelectedBucketId] = useState<string | null>(null)

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
    selectedBucketId,
    scopeIdsParam,
    adHocTagsParam,
    // useState setters are already referentially stable — no useCallback needed
    handleScopeChange: setSelectedScopeIds,
    handleTagChange: setSelectedTags,
    handleBucketChange: setSelectedBucketId,
  }
}
