import { useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { ChevronRight } from "lucide-react"
import type { ChatMessage } from "@/lib/types"
import { cn } from "@/lib/utils"

interface ThinkBlock {
  type: "think" | "text" | "thinking"
  content: string
}

function parseThinkBlocks(text: string): ThinkBlock[] {
  const blocks: ThinkBlock[] = []
  const regex = /<think>([\s\S]*?)<\/think>/gi
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      const before = text.slice(lastIndex, match.index)
      if (before.trim()) blocks.push({ type: "text", content: before })
    }
    blocks.push({ type: "think", content: match[1] })
    lastIndex = regex.lastIndex
  }

  const remaining = text.slice(lastIndex)
  const openTag = remaining.search(/<think>/i)
  if (openTag >= 0) {
    const before = remaining.slice(0, openTag)
    if (before.trim()) blocks.push({ type: "text", content: before })
    blocks.push({ type: "thinking", content: remaining.slice(openTag + 7) })
  } else if (remaining.trim()) {
    blocks.push({ type: "text", content: remaining })
  }

  return blocks
}

function ThinkCollapsible({
  content,
  isLive,
}: {
  content: string
  isLive: boolean
}) {
  const [open, setOpen] = useState(false)

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="my-2">
      <CollapsibleTrigger className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors">
        <ChevronRight
          className={cn("h-3 w-3 transition-transform", open && "rotate-90")}
        />
        {isLive ? (
          <span className="animate-pulse">Thinking...</span>
        ) : (
          "Thought process"
        )}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-1 pl-4 border-l-2 border-muted text-sm text-muted-foreground">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user"

  const blocks = !isUser ? parseThinkBlocks(message.content) : []
  const hasThink = blocks.some((b) => b.type !== "text")

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-4 py-2",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground",
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : hasThink ? (
          <div className="mdkb-prose">
            {blocks.map((block, i) =>
              block.type === "text" ? (
                <ReactMarkdown key={i} remarkPlugins={[remarkGfm]}>
                  {block.content}
                </ReactMarkdown>
              ) : (
                <ThinkCollapsible
                  key={i}
                  content={block.content}
                  isLive={block.type === "thinking"}
                />
              ),
            )}
          </div>
        ) : (
          <div className="mdkb-prose">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}
