import { useState, useCallback } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { api } from "@/lib/api"
import { toast } from "sonner"
import { ChevronDown, ChevronRight, Eye, Loader2, Tag, Wand2 } from "lucide-react"

interface PreviewRule {
  tag: string
  count: number
  paths: string[]
}

interface PreviewResult {
  strategy: string
  base_path: string
  depth: number
  tag_prefix: string
  rules: PreviewRule[]
  total_files: number
  total_tags: number
}

export function AutoTagDialog({
  open,
  onOpenChange,
  sources,
  onApplied,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  sources: string[]
  onApplied: () => void
}) {
  const [basePath, setBasePath] = useState(sources[0] ?? "")
  const [strategy, setStrategy] = useState<"subfolder" | "doc_type">("subfolder")
  const [depth, setDepth] = useState(1)
  const [tagPrefix, setTagPrefix] = useState("")
  const [preview, setPreview] = useState<PreviewResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const runPreview = useCallback(async () => {
    setLoading(true)
    setPreview(null)
    try {
      const res = await api.post<PreviewResult>("/api/v1/files/auto-tag-preview", {
        base_path: basePath,
        strategy,
        depth,
        tag_prefix: tagPrefix,
      })
      setPreview(res)
      setExpanded(new Set())
    } catch (err) {
      toast.error(`Preview failed: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }, [basePath, strategy, depth, tagPrefix])

  const applyPlan = useCallback(async () => {
    if (!preview) return
    setApplying(true)
    try {
      const plan: Record<string, string[]> = {}
      for (const rule of preview.rules) {
        plan[rule.tag] = rule.paths
      }
      const res = await api.post<{ updated: number }>("/api/v1/files/auto-tag-apply", { plan })
      toast.success(`Tagged ${res.updated} files across ${preview.total_tags} tags`)
      onApplied()
      onOpenChange(false)
    } catch (err) {
      toast.error(`Apply failed: ${(err as Error).message}`)
    } finally {
      setApplying(false)
    }
  }, [preview, onApplied, onOpenChange])

  const toggleExpand = (tag: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(tag)) next.delete(tag)
      else next.add(tag)
      return next
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Wand2 className="h-4 w-4" />
            Auto-Tag by Pattern
          </DialogTitle>
          <DialogDescription>
            Generate tags from folder structure. Preview before applying.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Base path */}
          <div className="space-y-1.5">
            <Label>Source directory</Label>
            <Select value={basePath} onValueChange={setBasePath}>
              <SelectTrigger className="cursor-pointer">
                <SelectValue placeholder="Select source..." />
              </SelectTrigger>
              <SelectContent>
                {sources.map((s) => (
                  <SelectItem key={s} value={s}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Strategy */}
          <div className="space-y-1.5">
            <Label>Strategy</Label>
            <Select value={strategy} onValueChange={(v) => setStrategy(v as "subfolder" | "doc_type")}>
              <SelectTrigger className="cursor-pointer">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="subfolder">
                  By subfolder name
                </SelectItem>
                <SelectItem value="doc_type">
                  By parent folder (doc type)
                </SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {strategy === "subfolder"
                ? `Tags files with the folder name at depth ${depth} below the source. e.g. source/my-project/... → "my-project"`
                : "Tags files with their immediate parent folder name. e.g. .../implementation_docs/FILE.md → \"implementation_docs\""}
            </p>
          </div>

          {/* Depth (only for subfolder strategy) */}
          {strategy === "subfolder" && (
            <div className="space-y-1.5">
              <Label>Folder depth</Label>
              <Select value={String(depth)} onValueChange={(v) => setDepth(Number(v))}>
                <SelectTrigger className="w-24 cursor-pointer">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 4, 5].map((d) => (
                    <SelectItem key={d} value={String(d)}>{d}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Tag prefix */}
          <div className="space-y-1.5">
            <Label>Tag prefix (optional)</Label>
            <Input
              value={tagPrefix}
              onChange={(e) => setTagPrefix(e.target.value)}
              placeholder='e.g. "project:" or leave empty'
              className="w-48"
            />
          </div>

          {/* Preview button */}
          <Button
            variant="outline"
            onClick={runPreview}
            disabled={loading || !basePath}
            className="cursor-pointer"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            ) : (
              <Eye className="h-3.5 w-3.5 mr-1.5" />
            )}
            {loading ? "Computing..." : "Preview"}
          </Button>

          {/* Preview results */}
          {preview && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">
                  {preview.total_tags} tags, {preview.total_files} files
                </span>
              </div>
              <ScrollArea className="max-h-[30vh] border rounded-md">
                <div className="p-2 space-y-1">
                  {preview.rules.map((rule) => (
                    <div key={rule.tag}>
                      <button
                        type="button"
                        className="flex items-center gap-2 w-full text-left px-2 py-1 rounded hover:bg-muted/50 cursor-pointer"
                        onClick={() => toggleExpand(rule.tag)}
                      >
                        {expanded.has(rule.tag) ? (
                          <ChevronDown className="h-3 w-3 shrink-0" />
                        ) : (
                          <ChevronRight className="h-3 w-3 shrink-0" />
                        )}
                        <Badge variant="secondary" className="gap-1">
                          <Tag className="h-2.5 w-2.5" />
                          {rule.tag}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {rule.count} files
                        </span>
                      </button>
                      {expanded.has(rule.tag) && (
                        <div className="ml-8 mt-1 mb-2 space-y-0.5">
                          {rule.paths.map((p) => (
                            <div key={p} className="text-xs text-muted-foreground truncate font-mono">
                              {p.split("/").pop()}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  {preview.rules.length === 0 && (
                    <p className="text-sm text-muted-foreground p-2">
                      No files matched. Try a different base path or strategy.
                    </p>
                  )}
                </div>
              </ScrollArea>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={applyPlan}
            disabled={!preview || preview.total_files === 0 || applying}
            className="cursor-pointer"
          >
            {applying ? (
              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            ) : (
              <Wand2 className="h-3.5 w-3.5 mr-1.5" />
            )}
            {applying ? "Applying..." : `Apply ${preview?.total_tags ?? 0} tags to ${preview?.total_files ?? 0} files`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
