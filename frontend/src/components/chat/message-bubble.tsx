import { useState, useMemo, memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronRight, Brain, FileText, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ChatMessage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog";

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

const plugins = [remarkGfm];

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
          <ReactMarkdown remarkPlugins={plugins}>{content}</ReactMarkdown>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export const MessageBubble = memo(function MessageBubble({
  message,
  showDiagnostics = false,
}: {
  message: ChatMessage;
  showDiagnostics?: boolean;
}) {
  const isUser = message.role === "user";
  const [viewingFile, setViewingFile] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
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
        {/* Diagnostics: raw content inspector for assistant messages */}
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
          <div className="mdkb-prose">
            {blocks.map((block, i) =>
              block.type === "text" ? (
                <div key={i} className="p-1 my-1">
                  <ReactMarkdown remarkPlugins={plugins}>
                    {block.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <div key={i} className="p-1 my-1">
                  <ThinkCollapsible
                    content={block.content}
                    isLive={block.type === "thinking"}
                  />
                </div>
              ),
            )}
          </div>
        ) : (
          <div className="mdkb-prose p-1">
            <ReactMarkdown remarkPlugins={plugins}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
        {(!isUser && (message.content || (sources && sources.length > 0))) && (
          <div className="flex items-center gap-1.5 mt-2 pt-2 border-t border-foreground/10">
            {sources && sources.length > 0 && (
              <>
                <span className="text-xs text-muted-foreground">
                  Sources:
                </span>
                {sources.map((src) => (
                  <button
                    key={src}
                    type="button"
                    onClick={() => setViewingFile(src)}
                    className="inline-flex items-center gap-1 text-xs bg-background/60 hover:bg-background px-2 py-0.5 rounded border border-border hover:border-primary/50 transition-colors cursor-pointer"
                  >
                    <FileText className="h-3 w-3 shrink-0" />
                    <span className="truncate max-w-[200px]">
                      {src.split("/").pop()}
                    </span>
                  </button>
                ))}
              </>
            )}
            <div className="flex-1" />
            <Button
              variant="ghost"
              size="icon"
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
      <FileViewerDialog path={viewingFile} onClose={() => setViewingFile(null)} />
    </div>
  );
});
