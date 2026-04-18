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
import { CodeBlock } from "@/components/ui/code-block"

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
          aria-label={`Citation ${num}: ${path}`}
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
  onLinkClick,
}: {
  children: string
  className?: string
  sourceMap?: Record<string, string>
  onCiteClick?: (path: string) => void
  /**
   * Called when a non-citation anchor is clicked. If the handler returns
   * true the default navigation is suppressed — use this for intercepting
   * relative markdown links (e.g. wiki index entries) and routing them
   * into an in-app viewer instead of the SPA fallback.
   */
  onLinkClick?: (href: string) => boolean
}) {
  const plugins = sourceMap ? citePlugins : basePlugins

  const components = useMemo(() => {
    const codeBlockComponent = {
      pre({ children }: React.HTMLAttributes<HTMLPreElement>) {
        // react-markdown wraps <code> in <pre>; unwrap to get language + content
        const codeEl = (children as React.ReactElement<React.HTMLAttributes<HTMLElement>> | undefined)
        const className = codeEl?.props?.className ?? ""
        const language = className.match(/language-(\w+)/)?.[1]
        const code = String(codeEl?.props?.children ?? "").replace(/\n$/, "")
        return <CodeBlock code={code} language={language} />
      },
      code({ className, children, ...props }: React.HTMLAttributes<HTMLElement>) {
        // Inline code (not inside a pre) — styled distinctly
        if (!className?.startsWith("language-")) {
          return (
            <code
              className="font-mono text-[0.85em] bg-zinc-100 dark:bg-zinc-800 text-pink-600 dark:text-pink-300 rounded px-1.5 py-0.5"
              {...props}
            >
              {children}
            </code>
          )
        }
        return <code className={className} {...props}>{children}</code>
      },
    }

    const anchorRenderer = ({ href, children: linkChildren, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
      const match = href?.match(/^#cite-(\d+)$/)
      if (match && sourceMap) {
        const num = match[1]!
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
      if (onLinkClick && href) {
        return (
          <a
            href={href}
            {...props}
            onClick={(e) => {
              if (onLinkClick(href)) e.preventDefault()
            }}
          >
            {linkChildren}
          </a>
        )
      }
      return <a href={href} {...props}>{linkChildren}</a>
    }

    if (!sourceMap && !onLinkClick) return codeBlockComponent
    return { ...codeBlockComponent, a: anchorRenderer }
  }, [sourceMap, onCiteClick, onLinkClick])

  // Fix LLM output where citations sit on the closing code fence line
  // (``` [1]) which breaks markdown parsing. Move citations to the
  // prose line before the code block opened.
  const cleaned = useMemo(() => {
    const lines = children.split("\n")
    const result: string[] = []
    let codeBlockStartIdx = -1 // index in result[] where the opening ``` is

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]!
      const fenceMatch = line.match(/^(```)(\w*)[ \t]*(\[[\d,\s\]]+])?[ \t]*$/)

      if (fenceMatch && codeBlockStartIdx === -1) {
        // Opening fence — remember where it started
        codeBlockStartIdx = result.length
        const cite = fenceMatch[3]
        if (cite && result.length > 0) {
          // Citation on opening fence — attach to previous prose line
          result[result.length - 1] += ` ${cite}`
          result.push("```" + (fenceMatch[2] ?? ""))
        } else {
          result.push(line)
        }
      } else if (fenceMatch && codeBlockStartIdx !== -1) {
        // Closing fence
        const cite = fenceMatch[3]
        result.push("```")
        if (cite && codeBlockStartIdx > 0) {
          // Move citation to the prose line before the code block
          result[codeBlockStartIdx - 1] += ` ${cite}`
        } else if (cite) {
          result.push(cite!)
        }
        codeBlockStartIdx = -1
      } else {
        result.push(line)
      }
    }
    return result.join("\n")
  }, [children])

  return (
    <div className={cn("markdownkb-prose", className)}>
      <ReactMarkdown remarkPlugins={plugins} components={components}>
        {cleaned}
      </ReactMarkdown>
    </div>
  )
}
