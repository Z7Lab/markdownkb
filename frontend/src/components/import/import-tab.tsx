import { useEffect, useMemo, useState } from "react"
import { api } from "@/lib/api"
import { useSettings } from "@/hooks/use-settings"
import { useImportCapabilities } from "@/hooks/use-import-capabilities"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import {
  Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { FilePlus, FolderOpen, Archive } from "lucide-react"
import { IngestionPanel, type IngestDestination } from "./ingestion-panel"
import { CreateMarkdownDialog } from "./create-markdown-dialog"

interface BucketOption { id: string; name: string }

/** Short, readable label for a source path (last two segments). */
function sourceLabel(path: string): string {
  const parts = path.replace(/\/$/, "").split("/").filter(Boolean)
  return parts.slice(-2).join("/") || path
}

export function ImportTab() {
  const { settings } = useSettings()
  const { find } = useImportCapabilities()
  const createAvailable = !!find("create_markdown")?.available

  const writableSources = useMemo(
    () => (settings?.source_configs ?? []).filter((s) => s.writable).map((s) => s.path),
    [settings],
  )
  const bucketsEnabled = !!settings?.plugins_enabled?.buckets

  const [buckets, setBuckets] = useState<BucketOption[]>([])
  useEffect(() => {
    if (!bucketsEnabled) { setBuckets([]); return }
    let active = true
    api.get<{ buckets: BucketOption[] }>("/api/v1/buckets")
      .then((r) => { if (active) setBuckets(r.buckets.map((b) => ({ id: b.id, name: b.name }))) })
      .catch(() => { if (active) setBuckets([]) })
    return () => { active = false }
  }, [bucketsEnabled])

  // Selected destination encoded as "source:<path>" or "bucket:<id>".
  const [selected, setSelected] = useState<string>("")
  const defaultKey = writableSources[0] ? `source:${writableSources[0]}` : ""
  const activeKey = selected || defaultKey

  const destination: IngestDestination | null = useMemo(() => {
    if (activeKey.startsWith("source:")) return { type: "source", path: activeKey.slice(7) }
    if (activeKey.startsWith("bucket:")) return { type: "bucket", id: activeKey.slice(7) }
    return null
  }, [activeKey])

  const [createOpen, setCreateOpen] = useState(false)

  const hasDestinations = writableSources.length > 0 || buckets.length > 0

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <header className="shrink-0 border-b px-6 py-3 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-base font-semibold flex items-center gap-2">
            <FilePlus className="h-4 w-4" /> Import content
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Add documents, web pages, audio, or notes to your knowledge base.
          </p>
        </div>
        {createAvailable && destination && (
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 shrink-0"
            onClick={() => setCreateOpen(true)}
            title="Write a new markdown note"
          >
            <FilePlus className="h-3.5 w-3.5" />
            New note
          </Button>
        )}
      </header>

      <ScrollArea className="flex-1 min-h-0">
        <div className="max-w-2xl mx-auto p-6 space-y-5">
          {!hasDestinations ? (
            <p className="text-sm text-muted-foreground">
              No writable destinations available. Add a writable source in Settings → Sources
              (read-only sources and project-root mounts can't receive imports).
            </p>
          ) : (
            <>
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-muted-foreground">Destination</p>
                <Select value={activeKey} onValueChange={setSelected}>
                  <SelectTrigger className="h-9 text-sm w-full">
                    <SelectValue placeholder="Choose where imports land" />
                  </SelectTrigger>
                  <SelectContent>
                    {writableSources.length > 0 && (
                      <SelectGroup>
                        <SelectLabel className="flex items-center gap-1.5">
                          <FolderOpen className="h-3.5 w-3.5" /> Source directories
                        </SelectLabel>
                        {writableSources.map((s) => (
                          <SelectItem key={`source:${s}`} value={`source:${s}`} className="text-sm">
                            <span title={s}>{sourceLabel(s)}</span>
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    )}
                    {buckets.length > 0 && (
                      <SelectGroup>
                        <SelectLabel className="flex items-center gap-1.5">
                          <Archive className="h-3.5 w-3.5" /> Buckets
                        </SelectLabel>
                        {buckets.map((b) => (
                          <SelectItem key={`bucket:${b.id}`} value={`bucket:${b.id}`} className="text-sm">
                            {b.name}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    )}
                  </SelectContent>
                </Select>
                {destination?.type === "source" && (
                  <p className="text-[11px] text-muted-foreground font-mono truncate" title={destination.path}>
                    {destination.path}
                  </p>
                )}
              </div>

              {destination && (
                <IngestionPanel destination={destination} />
              )}
            </>
          )}
        </div>
      </ScrollArea>

      {destination && (
        <CreateMarkdownDialog
          open={createOpen}
          destination={destination}
          onClose={() => setCreateOpen(false)}
        />
      )}
    </div>
  )
}
