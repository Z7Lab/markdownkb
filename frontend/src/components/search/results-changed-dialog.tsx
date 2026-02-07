import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { ScoreChange } from "@/lib/types"

interface ResultsChangedDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  missingFiles: string[]
  newFiles: string[]
  scoreChanges: ScoreChange[]
  storedResultCount: number
  currentResultCount: number
}

export function ResultsChangedDialog({
  open,
  onOpenChange,
  missingFiles,
  newFiles,
  scoreChanges,
  storedResultCount,
  currentResultCount,
}: ResultsChangedDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="!max-w-3xl">
        <AlertDialogHeader>
          <AlertDialogTitle>Results Changed</AlertDialogTitle>
          <AlertDialogDescription>
            The knowledge base has changed since this search was created.
            {storedResultCount !== currentResultCount && (
              <span className="block mt-1">
                Result count: {storedResultCount} → {currentResultCount}
              </span>
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <ScrollArea className="max-h-[60vh]">
          <div className="space-y-4 p-1">
            {/* Missing files */}
            {missingFiles.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2 text-destructive">
                  Removed from RAG ({missingFiles.length})
                </h3>
                <div className="space-y-1">
                  {missingFiles.map((path) => (
                    <div
                      key={path}
                      className="text-sm font-mono text-muted-foreground bg-destructive/10 px-2 py-1 rounded"
                    >
                      {path}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* New files */}
            {newFiles.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2 text-green-600 dark:text-green-400">
                  Added to RAG ({newFiles.length})
                </h3>
                <div className="space-y-1">
                  {newFiles.map((path) => (
                    <div
                      key={path}
                      className="text-sm font-mono text-muted-foreground bg-green-500/10 px-2 py-1 rounded"
                    >
                      {path}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Score changes */}
            {scoreChanges.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2">
                  Relevance Score Changes ({scoreChanges.length})
                </h3>
                <div className="space-y-2">
                  {scoreChanges.map((change) => (
                    <div
                      key={change.path}
                      className="flex items-center justify-between gap-2 text-sm bg-muted/50 px-3 py-2 rounded"
                    >
                      <span className="font-mono truncate flex-1">{change.path}</span>
                      <div className="flex items-center gap-2 shrink-0">
                        <Badge variant="secondary">
                          {Math.round(change.old_score * 100)}%
                        </Badge>
                        <span className="text-muted-foreground">→</span>
                        <Badge variant="secondary">
                          {Math.round(change.new_score * 100)}%
                        </Badge>
                        <Badge
                          variant={change.change > 0 ? "default" : "outline"}
                          className={
                            change.change > 0
                              ? "bg-green-500/20 text-green-600 dark:text-green-400"
                              : change.change < 0
                              ? "bg-destructive/20 text-destructive"
                              : ""
                          }
                        >
                          {change.change > 0 ? "+" : ""}
                          {Math.round(change.change * 100)}%
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        <AlertDialogFooter>
          <AlertDialogCancel>Close</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
