import { useState } from "react"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Loader2, FilePlus } from "lucide-react"
import { toast } from "sonner"
import { slugifyFilename } from "@/lib/utils"
import { api } from "@/lib/api"
import type { IngestDestination } from "./ingestion-panel"

/** Resolve the user's filename input to the actual `.md` filename that gets written. */
function resolveMarkdownFilename(name: string): string {
  const trimmed = name.trim()
  if (!trimmed) return ""
  if (trimmed.toLowerCase().endsWith(".md")) {
    // Slug the stem but keep the .md the user typed.
    return slugifyFilename(trimmed.slice(0, -3)) + ".md"
  }
  return slugifyFilename(trimmed) + ".md"
}

export interface CreateMarkdownDialogProps {
  open: boolean
  destination: IngestDestination
  onClose: () => void
  onCreated?: () => void
}

export function CreateMarkdownDialog({ open, destination, onClose, onCreated }: CreateMarkdownDialogProps) {
  const [name, setName] = useState("")
  const [body, setBody] = useState("")
  const [saving, setSaving] = useState(false)

  const filename = resolveMarkdownFilename(name)
  const canSave = !!filename && !!body.trim() && !saving

  const reset = () => { setName(""); setBody("") }

  const handleCreate = async () => {
    if (!canSave) return
    setSaving(true)
    try {
      if (destination.type === "source") {
        await api.post("/api/v1/documents", {
          path: filename, content: body, source: destination.path,
        })
      } else {
        await api.post(`/api/v1/buckets/${destination.id}/documents`, {
          documents: [{ name: filename, content: body }],
        })
      }
      toast.success(`Created "${filename}"`)
      reset()
      onCreated?.()
      onClose()
    } catch (err) {
      toast.error(`Create failed: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o && !saving) { reset(); onClose() } }}>
      <AlertDialogContent className="!max-w-4xl !h-[80vh] flex flex-col">
        <div className="px-6 pt-6">
          <AlertDialogTitle className="flex items-center gap-2 text-base">
            <FilePlus className="h-4 w-4" /> Create markdown note
          </AlertDialogTitle>
        </div>

        <div className="flex flex-col gap-2 px-6 flex-1 min-h-0">
          <div className="space-y-1">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Filename (e.g. meeting notes)"
              className="h-9"
              disabled={saving}
              aria-label="Document filename"
              autoFocus
            />
            <p className="text-[11px] text-muted-foreground">
              {filename
                ? <>Saves as <span className="font-mono">{filename}</span> (spaces become hyphens; <span className="font-mono">.md</span> added automatically)</>
                : "Spaces become hyphens and .md is added automatically."}
            </p>
          </div>
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder={"# Title\n\nWrite markdown content…"}
            className="flex-1 min-h-0 resize-none font-mono text-sm"
            disabled={saving}
            aria-label="Document content"
          />
        </div>

        <AlertDialogFooter className="px-6 pb-6">
          <AlertDialogCancel disabled={saving}>Cancel</AlertDialogCancel>
          <Button onClick={handleCreate} disabled={!canSave}>
            {saving ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <FilePlus className="h-3.5 w-3.5 mr-1.5" />}
            Create
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
