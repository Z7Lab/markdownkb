import { useState, useMemo, memo } from "react";
import { Markdown } from "@/components/ui/markdown";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronRight, Brain, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ChatMessage as ChatMessageType } from "@/lib/types";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { SourceList } from "@/components/ui/source-badge";

interface ThinkBlock {
  type: "think" | "text" | "thinking";
  content: string;
}

function parseThinkBlocks(text: string): ThinkBlock[] {
  const blocks: ThinkBlock[] = [];
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
  const openTagMatch = remaining.match(/<(think|thinking)>([\s\S]*)$/i);
  if (openTagMatch) {
    const before = remaining.slice(0, openTagMatch.index);
    if (before.trim()) blocks.push({ type: "text", content: before });
    blocks.push({ type: "thinking", content: openTagMatch[2] });
  } else {
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
        <Markdown className="mt-1 pl-4 border-l-2 border-foreground/20 text-sm text-foreground/60">
          {content}
        </Markdown>
      </CollapsibleContent>
    </Collapsible>
  );
}

export const ChatMessage = memo(function ChatMessage({
  message,
  showDiagnostics = false,
  onViewFile,
}: {
  message: ChatMessageType;
  showDiagnostics?: boolean;
  onViewFile?: (path: string) => void;
}) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Failed to copy — clipboard access denied")
    }
  }

  const blocks = useMemo(
    () => (!isUser ? parseThinkBlocks(message.content) : []),
    [isUser, message.content],
  );

  const hasThink = blocks.some((b) => b.type !== "text");
  const sources = message.sources;

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "rounded-lg px-4 py-2",
          isUser
            ? "max-w-[85%] bg-primary text-primary-foreground"
            : "w-full bg-muted text-foreground",
        )}
      >
        {showDiagnostics && !isUser && (
          <div className="text-[10px] font-mono bg-black/80 text-green-400 p-2 rounded mb-2 max-h-24 overflow-auto whitespace-pre-wrap break-all">
            <div>
              BLOCKS: {blocks.length} [{blocks.map((b) => b.type).join(", ")}]
            </div>
            <div>hasThink: {String(hasThink)}</div>
            <div>
              RAW[0..120]: {JSON.stringify(message.content.slice(0, 120))}
            </div>
            <div>
              HAS &lt;think&gt;: {String(message.content.includes("<think>"))}
            </div>
            <div>
              HAS &lt;thinking&gt;:{" "}
              {String(message.content.includes("<thinking>"))}
            </div>
          </div>
        )}
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : hasThink ? (
          <div>
            {blocks.map((block, i) =>
              block.type === "text" ? (
                <Markdown key={`text-${i}`} className="p-1 my-1">
                  {block.content}
                </Markdown>
              ) : (
                <div key={`think-${i}`} className="p-1 my-1">
                  <ThinkCollapsible
                    content={block.content}
                    isLive={block.type === "thinking"}
                  />
                </div>
              ),
            )}
          </div>
        ) : (
          <Markdown className="p-1">{message.content}</Markdown>
        )}
        {!isUser && (message.content || (sources && sources.length > 0)) && (
          <div className="flex flex-wrap items-center gap-1.5 mt-2 pt-2 border-t border-foreground/10">
            {sources && sources.length > 0 && onViewFile && (
              <SourceList sources={sources} onSelect={onViewFile} />
            )}
            <div className="flex-1" />
            <Button
              variant="ghost"
              size="icon"
              aria-label="Copy message"
              className="h-6 w-6 shrink-0 text-muted-foreground hover:text-foreground"
              onClick={handleCopy}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
});
