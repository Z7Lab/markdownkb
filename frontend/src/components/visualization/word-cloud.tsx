import { cn } from "@/lib/utils"

export function WordCloud({
  terms,
  activeTerm,
  onTermClick,
}: {
  terms: Record<string, number>
  activeTerm?: string
  onTermClick: (term: string) => void
}) {
  const entries = Object.entries(terms).sort((a, b) => b[1] - a[1])
  if (entries.length === 0) {
    return (
      <p className="text-xs text-muted-foreground text-center py-4">
        No terms available
      </p>
    )
  }

  const maxWeight = entries[0][1] || 1

  return (
    <div className="p-3 flex flex-wrap gap-1">
      {entries.map(([term, weight]) => {
        const scale = Math.max(0.7, (weight / maxWeight) * 1.4)
        const isActive = activeTerm === term
        return (
          <button
            key={term}
            onClick={() => onTermClick(term)}
            className={cn(
              "px-1.5 py-0.5 rounded cursor-pointer transition-colors",
              "hover:bg-accent text-foreground/80 hover:text-foreground",
              isActive && "bg-primary/20 text-primary font-medium",
            )}
            style={{ fontSize: `${scale}rem` }}
          >
            {term}
          </button>
        )
      })}
    </div>
  )
}
