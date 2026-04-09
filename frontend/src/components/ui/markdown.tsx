import { useMemo } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { remarkCitations } from "@/lib/remark-citations"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

const basePlugins = [remarkGfm]
const citePlugins = [remarkGfm, remarkCitations]

function CitationRef({
  num,
  path,
  onClick,
}: {
  num: string
  path: string
  onClick: () => void
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          className="inline-flex items-center justify-center text-[10px] font-semibold
                     bg-primary/10 text-primary hover:bg-primary/20 rounded px-1 min-w-[1.1rem]
                     align-super cursor-pointer transition-colors leading-none py-0.5"
        >
          {num}
        </button>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        className="max-w-md break-all text-xs font-mono"
      >
        {path}
      </TooltipContent>
    </Tooltip>
  )
}

export function Markdown({
  children,
  className,
  sourceMap,
  onCiteClick,
}: {
  children: string
  className?: string
  sourceMap?: Record<string, string>
  onCiteClick?: (path: string) => void
}) {
  const plugins = sourceMap ? citePlugins : basePlugins

  const components = useMemo(() => {
    if (!sourceMap) return undefined
    return {
      a: ({ href, children: linkChildren, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
        const match = href?.match(/^#cite-(\d+)$/)
        if (match) {
          const num = match[1]
          const path = sourceMap[num]
          if (path) {
            return (
              <CitationRef
                num={num}
                path={path}
                onClick={() => onCiteClick?.(path)}
              />
            )
          }
          // Unknown/hallucinated reference — render as dimmed text
          return (
            <span className="text-muted-foreground text-xs">[{num}]</span>
          )
        }
        // Normal links pass through
        return <a href={href} {...props}>{linkChildren}</a>
      },
    }
  }, [sourceMap, onCiteClick])

  return (
    <div className={cn("markdownkb-prose", className)}>
      <ReactMarkdown remarkPlugins={plugins} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
