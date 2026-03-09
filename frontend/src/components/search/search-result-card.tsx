import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Markdown } from "@/components/ui/markdown"
import { ChevronDown, ChevronRight } from "lucide-react"
import type { SearchResult } from "@/lib/types"

export function SearchResultCard({
  result,
  isExpanded,
  onToggleExpanded,
  onSelect,
}: {
  result: SearchResult
  isExpanded: boolean
  onToggleExpanded: (e: React.MouseEvent) => void
  onSelect: (path: string) => void
}) {
  const hasMultipleSnippets = (result.snippets?.length ?? 0) > 1

  return (
    <Card
      className="cursor-pointer hover:bg-accent/50 transition-colors"
      onClick={() => onSelect(result.metadata.source_path ?? "")}
    >
      <CardContent className="pt-4">
        <div className="flex items-center gap-2 mb-2">
          <Badge variant="secondary">
            {Math.round(result.score * 100)}%
          </Badge>
          {result.chunk_count && result.chunk_count > 1 && (
            <Badge variant="outline" className="text-xs">
              {result.chunk_count} sections
            </Badge>
          )}
          <span className="text-sm font-mono text-muted-foreground truncate flex-1">
            {result.metadata.source_path ?? "unknown"}
          </span>
          {hasMultipleSnippets && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 shrink-0"
              onClick={onToggleExpanded}
            >
              {isExpanded ? (
                <>
                  <ChevronDown className="h-3 w-3 mr-1" />
                  Hide sections
                </>
              ) : (
                <>
                  <ChevronRight className="h-3 w-3 mr-1" />
                  Show all sections
                </>
              )}
            </Button>
          )}
        </div>

        {hasMultipleSnippets && isExpanded ? (
          <div className="space-y-3 mt-3">
            {result.snippets!.map((snippet, si) => (
              <div key={si} className="border-l-2 border-primary/30 pl-3">
                {snippet.heading && (
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-primary">
                      {snippet.heading}
                    </span>
                    <Badge variant="outline" className="text-xs">
                      {Math.round(snippet.score * 100)}%
                    </Badge>
                  </div>
                )}
                <Markdown className="text-sm">
                  {snippet.text.length > 400 ? snippet.text.slice(0, 400) + "..." : snippet.text}
                </Markdown>
              </div>
            ))}
          </div>
        ) : (
          <Markdown className="text-sm">
            {result.document.length > 500 ? result.document.slice(0, 500) + "..." : result.document}
          </Markdown>
        )}
      </CardContent>
    </Card>
  )
}
