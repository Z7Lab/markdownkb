import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { cn } from "@/lib/utils"

const plugins = [remarkGfm]

export function Markdown({
  children,
  className,
}: {
  children: string
  className?: string
}) {
  return (
    <div className={cn("mdkb-prose", className)}>
      <ReactMarkdown remarkPlugins={plugins}>{children}</ReactMarkdown>
    </div>
  )
}
