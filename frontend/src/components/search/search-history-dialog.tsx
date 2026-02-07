import { useEffect, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Clock, FileText, Loader2 } from "lucide-react"
import type { SearchVersion } from "@/lib/types"

interface SearchHistoryDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  activeSearchId: string | null
  fetchVersions: (searchId: string) => Promise<SearchVersion[]>
  onSelectVersion: (version: SearchVersion) => void
}

export function SearchHistoryDialog({
  open,
  onOpenChange,
  activeSearchId,
  fetchVersions,
  onSelectVersion,
}: SearchHistoryDialogProps) {
  const [versions, setVersions] = useState<SearchVersion[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (open && activeSearchId) {
      setLoading(true)
      fetchVersions(activeSearchId).then((v) => {
        setVersions(v)
        setLoading(false)
      })
    }
  }, [open, activeSearchId, fetchVersions])

  function handleSelect(version: SearchVersion) {
    onSelectVersion(version)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="!max-w-lg">
        <DialogHeader>
          <DialogTitle>Search History</DialogTitle>
          <DialogDescription>
            Select a version to view its preserved results.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : versions.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No versions found.
          </p>
        ) : (
          <ScrollArea className="max-h-[50vh]">
            <div className="space-y-2 pr-2">
              {versions.map((version, i) => {
                const isActive = version.id === activeSearchId
                const isOriginal = !version.parent_id

                return (
                  <button
                    key={version.id}
                    onClick={() => handleSelect(version)}
                    className={`w-full text-left rounded-md border px-3 py-2.5 transition-colors hover:bg-accent/50 ${
                      isActive
                        ? "border-primary bg-primary/5"
                        : "border-border"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium">
                        {isOriginal ? "Original" : `Re-query #${i}`}
                      </span>
                      {isActive && (
                        <Badge variant="default" className="text-xs h-4 px-1.5">
                          viewing
                        </Badge>
                      )}
                      {isOriginal && (
                        <Badge variant="outline" className="text-xs h-4 px-1.5">
                          first
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(version.created_at).toLocaleString()}
                      </span>
                      {version.result_count != null && (
                        <span className="flex items-center gap-1">
                          <FileText className="h-3 w-3" />
                          {version.result_count} results
                        </span>
                      )}
                    </div>
                    {version.summary && (
                      <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2">
                        {version.summary}
                      </p>
                    )}
                  </button>
                )
              })}
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  )
}
