import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { streamPlan } from "@/lib/sse"
import { toast } from "sonner"
import type { PlanNode, SavedPlan, SkillInfo, SkillReview } from "@/lib/types"

interface Approach {
  content: string
  score: number
}

export function usePlanner() {
  const [plan, setPlan] = useState("")
  const [sources, setSources] = useState<string[]>([])
  const [tree, setTree] = useState<PlanNode | null>(null)
  const [approaches, setApproaches] = useState<Approach[]>([])
  const [reviews, setReviews] = useState<SkillReview[]>([])
  const [refinedPlan, setRefinedPlan] = useState("")
  const [statusMessage, setStatusMessage] = useState("")
  const [phase, setPhase] = useState("")
  const [isPlanning, setIsPlanning] = useState(false)
  const [isRefined, setIsRefined] = useState(false)
  const [skills, setSkills] = useState<SkillInfo[]>([])
  const [query, setQuery] = useState("")

  // History
  const [savedPlans, setSavedPlans] = useState<SavedPlan[]>([])
  const [activePlanId, setActivePlanId] = useState<string | null>(null)

  const controllerRef = useRef<AbortController | null>(null)

  /** Reset all generation-related state (shared by generatePlan, clear, loadPlan) */
  const resetGeneration = useCallback(() => {
    controllerRef.current?.abort()
    setPlan("")
    setSources([])
    setTree(null)
    setApproaches([])
    setReviews([])
    setRefinedPlan("")
    setStatusMessage("")
    setPhase("")
    setIsPlanning(false)
    setIsRefined(false)
  }, [])

  /** Stop streaming and clear status (shared by onDone, onError, stop) */
  const finishStreaming = useCallback(() => {
    setIsPlanning(false)
    setStatusMessage("")
    setPhase("")
  }, [])

  const loadSkills = useCallback(async () => {
    try {
      const res = await api.get<{ skills: SkillInfo[] }>("/api/planner/skills")
      setSkills(res.skills)
    } catch {
      // Skills endpoint may not be available if feature is disabled
    }
  }, [])

  const refreshPlans = useCallback(async () => {
    try {
      const res = await api.get<{ plans: SavedPlan[] }>("/api/planner/plans")
      setSavedPlans(res.plans)
    } catch {
      // Plans endpoint may fail on first load
    }
  }, [])

  useEffect(() => {
    loadSkills()
    refreshPlans()
    return () => {
      controllerRef.current?.abort()
    }
  }, [loadSkills, refreshPlans])

  const generatePlan = useCallback((
    request: string,
    options?: { iterations?: number; n_approaches?: number; skill_names?: string[]; scope_ids?: string | null; ad_hoc_tags?: string[] | null },
  ) => {
    if (!request.trim()) return

    resetGeneration()
    setIsPlanning(true)
    setActivePlanId(null)
    setQuery(request.trim())

    controllerRef.current = streamPlan(
      request.trim(),
      {
        onStatus: (p, msg) => {
          setPhase(p)
          setStatusMessage(msg)
        },
        onApproach: (content, score) => {
          setApproaches((prev) => [...prev, { content, score }])
        },
        onPlan: (p) => setPlan(p),
        onSources: (s) => setSources(s),
        onTree: (t) => setTree(t),
        onReviews: (revs, refined) => {
          setReviews(revs)
          setRefinedPlan(refined)
          setIsRefined(true)
        },
        onDone: () => {
          finishStreaming()
        },
        onError: (err) => {
          finishStreaming()
          toast.error(`Plan generation failed: ${err.message}`)
        },
      },
      options,
    )
  }, [resetGeneration, finishStreaming])

  const stop = useCallback(() => {
    controllerRef.current?.abort()
    finishStreaming()
  }, [finishStreaming])

  const clear = useCallback(() => {
    resetGeneration()
    setActivePlanId(null)
    setQuery("")
  }, [resetGeneration])

  const savePlan = useCallback(async () => {
    const content = isRefined && refinedPlan ? refinedPlan : plan
    if (!content) {
      toast.error("No plan to save")
      return
    }
    const title = query ? `Plan: ${query.slice(0, 80)}` : "Untitled Plan"
    try {
      const res = await api.post<{ id: string }>("/api/planner/plans", {
        title,
        content,
        query,
      })
      setActivePlanId(res.id)
      await refreshPlans()
      toast.success("Plan saved")
    } catch (err) {
      toast.error(`Failed to save plan: ${(err as Error).message}`)
    }
  }, [plan, refinedPlan, isRefined, query, refreshPlans])

  const loadPlan = useCallback(async (planId: string) => {
    try {
      const res = await api.get<{ id: string; title: string; content: string; query: string }>(
        `/api/planner/plans/${planId}`,
      )
      // Clear generation state, show saved plan
      resetGeneration()
      setPlan(res.content)
      setQuery(res.query || res.title.replace(/^Plan:\s*/, ""))
      setActivePlanId(planId)
    } catch (err) {
      toast.error(`Failed to load plan: ${(err as Error).message}`)
    }
  }, [resetGeneration])

  const deletePlan = useCallback(async (planId: string) => {
    try {
      await api.del(`/api/planner/plans/${planId}`)
      if (activePlanId === planId) {
        clear()
      }
      await refreshPlans()
      toast.success("Plan deleted")
    } catch (err) {
      toast.error(`Failed to delete plan: ${(err as Error).message}`)
    }
  }, [activePlanId, clear, refreshPlans])

  return {
    plan, sources, tree, approaches, reviews, refinedPlan,
    statusMessage, phase, isPlanning, isRefined, skills, query,
    savedPlans, activePlanId,
    generatePlan, loadSkills, stop, clear, savePlan, loadPlan, deletePlan,
  }
}
