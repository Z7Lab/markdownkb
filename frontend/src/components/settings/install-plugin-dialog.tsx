import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { AlertCircle, Download, Loader2 } from "lucide-react"
import { api } from "@/lib/api"
import { toast } from "sonner"

export function InstallPluginDialog({
  open,
  onOpenChange,
  onInstalled,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onInstalled: () => void
}) {
  const [url, setUrl] = useState("")
  const [installing, setInstalling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleInstall = async () => {
    if (!url.trim()) return
    setInstalling(true)
    setError(null)
    try {
      const res = await api.post<{ name: string; message: string }>("/api/v1/plugins/install", { url: url.trim() })
      toast.success(res.message || `Plugin '${res.name}' installed`)
      setUrl("")
      onInstalled()
      onOpenChange(false)
    } catch (err) {
      const msg = (err as Error).message
      setError(msg)
      toast.error(`Install failed: ${msg}`)
    } finally {
      setInstalling(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Install Plugin</DialogTitle>
          <DialogDescription>
            Point to a GitHub repository or a local directory containing a MarkdownKB plugin.
            The plugin must have an __init__.py with FEATURE_FLAG and router exports.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="plugin-url">GitHub URL or local path</Label>
            <Input
              id="plugin-url"
              value={url}
              onChange={(e) => { setUrl(e.target.value); setError(null) }}
              placeholder="https://github.com/user/repo or /path/to/plugin"
              onKeyDown={(e) => e.key === "Enter" && handleInstall()}
            />
            {error && (
              <p className="text-xs text-destructive flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {error}
              </p>
            )}
          </div>
          <div className="text-xs text-muted-foreground space-y-1">
            <p className="font-medium">Supported formats:</p>
            <ul className="list-disc list-inside space-y-0.5 ml-1">
              <li><code className="text-xs">https://github.com/user/repo</code> — entire repo as plugin</li>
              <li><code className="text-xs">https://github.com/user/repo/tree/main/path/to/plugin</code> — subdirectory</li>
              <li><code className="text-xs">user/repo</code> — shorthand for github.com</li>
              <li><code className="text-xs">/path/to/plugin</code> — local directory (absolute or relative)</li>
            </ul>
          </div>
          <div className="bg-muted/50 rounded-md p-3 text-xs text-muted-foreground space-y-1.5">
            <p className="font-medium text-foreground">Plugin requirements:</p>
            <ul className="list-disc list-inside space-y-0.5 ml-1">
              <li>__init__.py with <code>FEATURE_FLAG</code> and <code>router</code></li>
              <li>plugin.yaml manifest (recommended)</li>
              <li>requirements.txt for dependencies (optional)</li>
            </ul>
            <p className="mt-2">
              After installing, enable the feature flag and restart the container to activate.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleInstall} disabled={installing || !url.trim()}>
            {installing ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                Installing...
              </>
            ) : (
              <>
                <Download className="h-3.5 w-3.5 mr-1.5" />
                Install
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
