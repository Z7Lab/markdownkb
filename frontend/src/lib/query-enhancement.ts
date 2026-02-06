import { api } from "./api"

export interface EnhancedQuery {
  enhanced: boolean
  original_query: string
  enhanced_query: string
  keywords: string[]
  expanded_terms: Record<string, string>
  context: string
  error?: string
}

/**
 * Enhance a search query using LLM to extract keywords and expand acronyms.
 *
 * This is a reusable utility that can be called from anywhere in the app
 * (search, chat, etc.) to improve query understanding.
 *
 * Falls back gracefully if intelligent search is disabled or LLM is offline.
 */
export async function enhanceQuery(query: string): Promise<EnhancedQuery> {
  try {
    const result = await api.post<EnhancedQuery>("/api/search/enhance-query", {
      query,
      top_k: 5, // Not used for enhancement, but required by SearchRequest schema
    })
    return result
  } catch (error) {
    // Graceful fallback on error
    return {
      enhanced: false,
      original_query: query,
      enhanced_query: query,
      keywords: [],
      expanded_terms: {},
      context: "",
      error: error instanceof Error ? error.message : "Unknown error",
    }
  }
}

/**
 * Check if query enhancement resulted in any improvements.
 */
export function isEnhanced(result: EnhancedQuery): boolean {
  return (
    result.enhanced &&
    (result.keywords.length > 0 ||
      Object.keys(result.expanded_terms).length > 0 ||
      result.context.length > 0)
  )
}
