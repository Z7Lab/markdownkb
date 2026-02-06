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
    >
      <div className={cn("flex items-center gap-1", className?.includes("text-center") && "justify-center")}>
        {children}
        {active &&
          (sortDir === "asc" ? (
            <ArrowUp className="h-3.5 w-3.5" />
          ) : (
            <ArrowDown className="h-3.5 w-3.5" />
          ))}
      </div>
    </TableHead>
  )
}
