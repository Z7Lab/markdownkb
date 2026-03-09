import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Markdown } from "@/components/ui/markdown"
import { ChevronDown, ChevronRight, ShieldCheck } from "lucide-react"
import type { SkillReview } from "@/lib/types"

export function PlannerSkillReview({
  reviews,
}: {
  reviews: SkillReview[]
}) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  function toggle(idx: number) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) {
        next.delete(idx)
      } else {
        next.add(idx)
      }
      return next
    })
  }

  if (reviews.length === 0) return null

  return (
    <div>
      <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Skill Reviews</h3>
      <div className="space-y-2">
        {reviews.map((r, i) => (
          <Card key={i}>
            <CardContent className="pt-3 pb-3">
              <button
                className="flex items-center gap-2 w-full text-left"
                onClick={() => toggle(i)}
              >
                <ShieldCheck className="h-4 w-4 text-primary shrink-0" />
                <span className="text-sm font-medium flex-1">{r.skill_name}</span>
                {r.issues.length > 0 && (
                  <Badge variant="destructive" className="text-xs">
                    {r.issues.length} issue{r.issues.length > 1 ? "s" : ""}
                  </Badge>
                )}
                {r.approvals.length > 0 && (
                  <Badge variant="secondary" className="text-xs">
                    {r.approvals.length} approved
                  </Badge>
                )}
                {expanded.has(i) ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                )}
              </button>
              {expanded.has(i) && (
                <div className="mt-3 border-t pt-3">
                  <Markdown className="text-sm">{r.review}</Markdown>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
