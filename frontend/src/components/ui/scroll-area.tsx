import * as React from "react"

import { cn } from "@/lib/utils"

type ScrollAreaProps = React.HTMLAttributes<HTMLDivElement>

function ScrollArea({ className, children, ...props }: ScrollAreaProps) {
  return (
    <div
      data-slot="scroll-area"
      className={cn("relative overflow-y-auto", className)}
      {...props}
    >
      {children}
    </div>
  )
}

function ScrollBar(_: { className?: string; orientation?: "vertical" | "horizontal" }) {
  return null
}

export { ScrollArea, ScrollBar }
