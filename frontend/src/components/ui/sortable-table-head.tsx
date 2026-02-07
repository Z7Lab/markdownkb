import { ArrowDown, ArrowUp } from "lucide-react"
import { TableHead } from "@/components/ui/table"
import { cn } from "@/lib/utils"

export function SortableTableHead({
  sortKey,
  activeSortKey,
  sortDir,
  onSort,
  children,
  className,
}: {
  sortKey: string
  activeSortKey: string | null
  sortDir: "asc" | "desc"
  onSort: (key: string) => void
  children: React.ReactNode
  className?: string
}) {
  const active = activeSortKey === sortKey

  return (
    <TableHead
      onClick={() => onSort(sortKey)}
      className={cn("cursor-pointer select-none", className)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onSort(sortKey)
        }
      }}
      aria-label={`Sort by ${children}${active ? ` (currently ${sortDir === "asc" ? "ascending" : "descending"})` : ""}`}
    >
      <div className={cn("flex items-center gap-1", className?.includes("text-center") && "justify-center")}>
        {children}
        {active &&
          (sortDir === "asc" ? (
            <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
          ))}
      </div>
    </TableHead>
  )
}
