import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Markdown } from "@/components/ui/markdown"
import { ChevronDown, ChevronRight } from "lucide-react"
import { SourceBadge } from "@/components/ui/source-badge"
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
  const snippets = result.snippets ?? []
  const hasMultipleSnippets = snippets.length > 1
  const path = result.metadata.source_path ?? "unknown"

  // Best available preview text: first snippet text, then document field
  const previewText = snippets[0]?.text || result.document
  const truncated = previewText.length > 500
    ? previewText.slice(0, 500) + "..."
    : previewText

  return (
    <Card
      className="cursor-pointer hover:bg-accent/50 transition-colors"
      onClick={() => onSelect(path)}
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
          <SourceBadge
            path={path}
            onClick={(e) => {
              e?.stopPropagation()
              onSelect(path)
            }}
          />
          <div className="flex-1" />
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
            {snippets.map((snippet, si) => (
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
          <Markdown className="text-sm">{truncated}</Markdown>
        )}
      </CardContent>
    </Card>
  )
}
