import { useCallback, useEffect, useRef, useState } from "react"
import { api } from "@/lib/api"
import { streamPlan } from "@/lib/sse"
import { toast } from "sonner"
import type { PlanNode, SkillInfo, SkillReview } from "@/lib/types"

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

  const controllerRef = useRef<AbortController | null>(null)

  const loadSkills = useCallback(async () => {
    try {
      const res = await api.get<{ skills: SkillInfo[] }>("/api/planner/skills")
      setSkills(res.skills)
    } catch {
      // Skills endpoint may not be available if feature is disabled
    }
  }, [])

  useEffect(() => {
    loadSkills()
    return () => {
      controllerRef.current?.abort()
    }
  }, [loadSkills])

  const generatePlan = useCallback((
    request: string,
    options?: { iterations?: number; n_approaches?: number; skill_names?: string[] },
  ) => {
    if (!request.trim()) return

    // Reset state
    controllerRef.current?.abort()
    setPlan("")
    setSources([])
    setTree(null)
    setApproaches([])
    setReviews([])
    setRefinedPlan("")
    setStatusMessage("")
    setPhase("")
    setIsRefined(false)
    setIsPlanning(true)

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
        onTree: (t) => setTree(t as unknown as PlanNode),
        onReviews: (revs, refined) => {
          setReviews(revs as unknown as SkillReview[])
          setRefinedPlan(refined)
          setIsRefined(true)
        },
        onDone: () => {
          setIsPlanning(false)
          setStatusMessage("")
          setPhase("")
        },
        onError: (err) => {
          setIsPlanning(false)
          setStatusMessage("")
          setPhase("")
          toast.error(`Plan generation failed: ${err.message}`)
        },
      },
      options,
    )
  }, [])

  const stop = useCallback(() => {
    controllerRef.current?.abort()
    setIsPlanning(false)
    setStatusMessage("")
    setPhase("")
  }, [])

  const clear = useCallback(() => {
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

  return {
    plan, sources, tree, approaches, reviews, refinedPlan,
    statusMessage, phase, isPlanning, isRefined, skills,
    generatePlan, loadSkills, stop, clear,
  }
}
