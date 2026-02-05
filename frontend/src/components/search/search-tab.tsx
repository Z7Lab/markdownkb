import { useSearch } from "@/hooks/use-search"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Search } from "lucide-react"
import type { KeyboardEvent } from "react"

export function SearchTab() {
  const {
    query, setQuery,
    folder, setFolder,
    tag, setTag,
    results, folders, tags,
    loading, search,
  } = useSearch()

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") search()
  }

  return (
    <div className="flex flex-col h-full gap-4 p-4">
      <div className="flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search your knowledge base..."
          className="flex-1"
        />
        <Select value={folder ?? "_all"} onValueChange={(v) => setFolder(v === "_all" ? null : v)}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Folder" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">(all folders)</SelectItem>
            {folders.map((f) => (
              <SelectItem key={f} value={f}>{f}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={tag ?? "_all"} onValueChange={(v) => setTag(v === "_all" ? null : v)}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Tag" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">(all tags)</SelectItem>
            {tags.map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button onClick={search} disabled={loading || !query.trim()}>
          <Search className="h-4 w-4 mr-1.5" />
          Search
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-3">
          {results.length === 0 && !loading && (
            <p className="text-muted-foreground text-center py-8">
              {query ? "No results found." : "Enter a query to search."}
            </p>
          )}
          {results.map((r, i) => (
            <Card key={i}>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="secondary">
                    {r.score.toFixed(3)}
                  </Badge>
                  <span className="text-sm font-mono text-muted-foreground truncate">
                    {r.metadata.source_path ?? "unknown"}
                  </span>
                  {r.metadata.heading && (
                    <span className="text-sm text-muted-foreground">
                      | {r.metadata.heading}
                    </span>
                  )}
                </div>
                <p className="text-sm whitespace-pre-wrap">
                  {r.document.slice(0, 500)}
                  {r.document.length > 500 && "..."}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
