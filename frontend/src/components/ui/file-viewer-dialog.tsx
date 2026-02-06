import { useEffect, useState } from "react"
import { api } from "@/lib/api"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Markdown } from "@/components/ui/markdown"

export function FileViewerDialog({
  path,
  onClose,
}: {
  path: string | null
  onClose: () => void
}) {
  const [content, setContent] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!path) return
    setLoading(true)
    setContent("")
    api
      .get<{ content: string }>(`/api/file?path=${encodeURIComponent(path)}`)
      .then((res) => setContent(res.content))
      .catch(() => setContent("Error loading file."))
      .finally(() => setLoading(false))
  }, [path])

  const filename = path?.split("/").pop() ?? ""

  return (
    <AlertDialog open={!!path} onOpenChange={(open) => { if (!open) onClose() }}>
      <AlertDialogContent className="!max-w-4xl !h-[80vh] flex flex-col">
        <AlertDialogHeader>
          <AlertDialogTitle className="font-mono text-sm truncate">
            {filename}
          </AlertDialogTitle>
          <p className="text-xs text-muted-foreground truncate">{path}</p>
        </AlertDialogHeader>
        <ScrollArea className="flex-1 min-h-0 border rounded-md p-4">
          {loading ? (
            <p className="text-sm text-muted-foreground animate-pulse">
              Loading...
            </p>
          ) : (
            <Markdown>{content}</Markdown>
          )}
        </ScrollArea>
        <AlertDialogFooter>
          <AlertDialogCancel>Close</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
