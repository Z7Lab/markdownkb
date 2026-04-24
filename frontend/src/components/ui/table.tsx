import * as React from "react"
import { ArrowUp, ArrowDown } from "lucide-react"

import { cn } from "@/lib/utils"

function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div
      data-slot="table-container"
      className="relative w-full overflow-x-auto"
    >
      <table
        data-slot="table"
        className={cn("w-full caption-bottom text-sm", className)}
        {...props}
      />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn("[&_tr]:border-b", className)}
      {...props}
    />
  )
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody
      data-slot="table-body"
      className={cn("[&_tr:last-child]:border-0", className)}
      {...props}
    />
  )
}

function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn(
        "bg-muted/50 border-t font-medium [&>tr]:last:border-b-0",
        className
      )}
      {...props}
    />
  )
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "hover:bg-muted/50 data-[state=selected]:bg-muted border-b transition-colors",
        className
      )}
      {...props}
    />
  )
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "text-foreground h-10 px-2 text-left align-middle font-medium whitespace-nowrap [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]",
        className
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "p-2 align-middle whitespace-nowrap [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]",
        className
      )}
      {...props}
    />
  )
}

function TableCaption({
  className,
  ...props
}: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("text-muted-foreground mt-4 text-sm", className)}
      {...props}
    />
  )
}

interface SortProps {
  sortKey: string
  activeSortKey: string | null
  sortDir: "asc" | "desc"
  onSort: (key: string) => void
  children: React.ReactNode
  className?: string
}

/** Standalone sort button — use inside any container (div, th, etc.) */
function SortButton({ sortKey, activeSortKey, sortDir, onSort, children, className }: SortProps) {
  const active = activeSortKey === sortKey
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      className={cn(
        "flex items-center gap-1 font-medium text-foreground cursor-pointer select-none whitespace-nowrap overflow-hidden",
        className,
      )}
      aria-label={active ? `Sort by ${sortKey}, ${sortDir === "asc" ? "ascending" : "descending"}` : `Sort by ${sortKey}`}
    >
      {children}
      {active && (sortDir === "asc"
        ? <ArrowUp className="h-3 w-3" aria-hidden="true" />
        : <ArrowDown className="h-3 w-3" aria-hidden="true" />)}
    </button>
  )
}

/** TableHead with an embedded SortButton — use inside a Table component */
function SortableTableHead({ className, ...props }: SortProps) {
  return (
    <TableHead className={className}>
      <SortButton {...props} className="h-full w-full" />
    </TableHead>
  )
}

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
  SortButton,
  SortableTableHead,
}
