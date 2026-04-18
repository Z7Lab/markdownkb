import { useCallback, useRef, useState } from "react"
import { streamSearchSummary } from "@/lib/sse"
import { toast } from "sonner"

interface SummaryState {
  text: string
  sources: string[]
  isActive: boolean
  status: string | null
  iteration: number
  totalIterations: number
  model: string | null
  provider: string | null
}

const INITIAL: SummaryState = {
  text: "", sources: [], isActive: false, status: null, iteration: 0, totalIterations: 0,
  model: null, provider: null,
}

export function useSearchSummary(
  scopeIds?: string | null,
  adHocTags?: string[] | null,
  deepResearch = false,
  deepResearchIterations = 3,
) {
  const [state, setState] = useState<SummaryState>(INITIAL)
  const controllerRef = useRef<AbortController | null>(null)

  const reset = useCallback(() => {
    controllerRef.current?.abort()
    setState(INITIAL)
  }, [])

  const start = useCallback((query: string, options: { search_id?: string | null }) => {
    setState((s) => ({ ...s, isActive: true, status: null, iteration: 0, totalIterations: 0 }))
    controllerRef.current = streamSearchSummary(
      query,
      {
        onToken: (delta) => setState((s) => ({ ...s, text: s.text + delta, status: null })),
        onSources: (sources) => setState((s) => ({ ...s, sources })),
        onStatus: (_phase, message, iteration, totalIterations) => {
          setState((s) => ({
            ...s,
            status: message,
            ...(iteration !== undefined ? { iteration } : {}),
            ...(totalIterations !== undefined ? { totalIterations } : {}),
          }))
        },
        onDone: (meta) => setState((s) => ({ ...s, isActive: false, status: null, model: meta?.model ?? null, provider: meta?.provider ?? null })),
        onError: (err) => {
          setState((s) => ({ ...s, isActive: false, status: null }))
          toast.error(`Summary failed: ${err.message}`)
        },
      },
      {
        ...options,
        scope_ids: scopeIds,
        ad_hoc_tags: adHocTags,
        deep_research: deepResearch,
        deep_research_iterations: deepResearch ? deepResearchIterations : undefined,
      },
    )
  }, [scopeIds, adHocTags, deepResearch, deepResearchIterations])

  const stop = useCallback(() => {
    controllerRef.current?.abort()
    setState((s) => ({ ...s, isActive: false, status: null, iteration: 0, totalIterations: 0 }))
  }, [])

  const abort = useCallback(() => {
    controllerRef.current?.abort()
  }, [])

  return {
    summary: state.text,
    summarySources: state.sources,
    summaryStatus: state.status,
    isSummarizing: state.isActive,
    summaryIteration: state.iteration,
    summaryTotalIterations: state.totalIterations,
    summaryModel: state.model,
    summaryProvider: state.provider,
    resetSummary: reset,
    startSummary: start,
    stopSummary: stop,
    abortSummary: abort,
    setSummaryState: setState,
  }
}

export type { SummaryState }
export { INITIAL as INITIAL_SUMMARY }
