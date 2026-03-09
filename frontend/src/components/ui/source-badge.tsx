import { FileText } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * A clickable badge showing a source file's name with a tooltip for the full path.
 * Used across chat, search, and planner tabs for consistent source rendering.
 */
export function SourceBadge({
  path,
  onClick,
}: {
  path: string;
  onClick: (e?: React.MouseEvent) => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          className="inline-flex items-center gap-1 text-xs bg-background/60 hover:bg-background px-2 py-0.5 rounded border border-border hover:border-primary/50 transition-colors cursor-pointer"
        >
          <FileText className="h-3 w-3 shrink-0" />
          <span className="truncate max-w-[200px]">
            {path.split("/").pop()}
          </span>
        </button>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        className="max-w-md break-all text-xs font-mono"
      >
        {path}
      </TooltipContent>
    </Tooltip>
  );
}

/**
 * Renders a list of source badges with an optional label and flex-wrap layout.
 */
export function SourceList({
  sources,
  onSelect,
  label = "Sources:",
  className,
}: {
  sources: string[];
  onSelect: (path: string) => void;
  label?: string | false;
  className?: string;
}) {
  if (sources.length === 0) return null;

  return (
    <div className={className ?? "flex flex-wrap items-center gap-1.5"}>
      {label && (
        <span className="text-xs text-muted-foreground">{label}</span>
      )}
      {sources.map((src) => (
        <SourceBadge key={src} path={src} onClick={() => onSelect(src)} />
      ))}
    </div>
  );
}
