import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronRight, Brain } from "lucide-react";
import type { ChatMessage } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ThinkBlock {
  type: "think" | "text" | "thinking";
  content: string;
}

function parseThinkBlocks(text: string): ThinkBlock[] {
  const blocks: ThinkBlock[] = [];
  // Handle both <think>...</think> and <thinking>...</thinking> tags
  const regex = /<(think|thinking)>([\s\S]*?)<\/\1>/gi;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let lastWasThink = false;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      const before = text.slice(lastIndex, match.index);
      if (before.trim()) blocks.push({ type: "text", content: before });
    }
    blocks.push({ type: "think", content: match[2] });
    lastIndex = regex.lastIndex;
    lastWasThink = true;
  }

  let remaining = text.slice(lastIndex);
  // Check for unclosed thinking tags
  const openTagMatch = remaining.match(/<(think|thinking)>([\s\S]*)$/i);
  if (openTagMatch) {
    const before = remaining.slice(0, openTagMatch.index);
    if (before.trim()) blocks.push({ type: "text", content: before });
    blocks.push({ type: "thinking", content: openTagMatch[2] });
  } else {
    // Strip leading colons/whitespace left by some models after </think>
    if (lastWasThink) {
      remaining = remaining.replace(/^[\s:]+/, "");
    }
    if (remaining.trim()) {
      blocks.push({ type: "text", content: remaining });
    }
  }

  return blocks;
}

function ThinkCollapsible({
  content,
  isLive,
}: {
  content: string;
  isLive: boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="my-2">
      <CollapsibleTrigger className="flex items-center gap-1.5 text-sm text-foreground/60 hover:text-foreground transition-colors py-1">
        <Brain className="h-3.5 w-3.5" />
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
        <div className="mt-1 pl-4 border-l-2 border-foreground/20 text-sm text-foreground/60">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  const blocks = !isUser ? parseThinkBlocks(message.content) : [];
  const hasThink = blocks.some((b) => b.type !== "text");

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[70%] rounded-lg px-4 py-2",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground",
        )}
      >
        {/* DEBUG: raw content inspector for assistant messages */}
        {!isUser && (
          <div className="text-[10px] font-mono bg-black/80 text-green-400 p-2 rounded mb-2 max-h-24 overflow-auto whitespace-pre-wrap break-all">
            <div>BLOCKS: {blocks.length} [{blocks.map(b => b.type).join(", ")}]</div>
            <div>hasThink: {String(hasThink)}</div>
            <div>RAW[0..120]: {JSON.stringify(message.content.slice(0, 120))}</div>
            <div>HAS &lt;think&gt;: {String(message.content.includes("<think>"))}</div>
            <div>HAS &lt;thinking&gt;: {String(message.content.includes("<thinking>"))}</div>
          </div>
        )}
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : hasThink ? (
          <div className="mdkb-prose">
            {blocks.map((block, i) =>
              block.type === "text" ? (
                <div key={i} className="border-2 border-green-500 border-dashed p-1 my-1">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {block.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <div key={i} className={cn("border-2 border-dashed p-1 my-1", block.type === "thinking" ? "border-blue-500" : "border-red-500")}>
                  <ThinkCollapsible
                    content={block.content}
                    isLive={block.type === "thinking"}
                  />
                </div>
              ),
            )}
          </div>
        ) : (
          <div className="mdkb-prose border-2 border-yellow-500 border-dashed p-1">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
