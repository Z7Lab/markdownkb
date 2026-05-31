import { useMemo, useState } from "react"
import { useSettings } from "@/hooks/use-settings"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { FilePlus } from "lucide-react"
import { IngestionPanel } from "./ingestion-panel"

export function ImportTab() {
  const { settings } = useSettings()
  const writableSources = useMemo(
    () => (settings?.source_configs ?? []).filter((s) => s.writable).map((s) => s.path),
    [settings],
  )
  const [dest, setDest] = useState<string>("")
  const selected = dest || writableSources[0] || ""

  return (
    <div className="flex h-full overflow-hidden">
      <ScrollArea className="flex-1 min-h-0">
        <div className="max-w-2xl mx-auto p-6 space-y-5">
          <div className="space-y-1">
            <h1 className="text-lg font-semibold flex items-center gap-2">
              <FilePlus className="h-5 w-5" /> Import content
            </h1>
            <p className="text-sm text-muted-foreground">
              Add documents, web pages, audio, or notes to your knowledge base.
            </p>
          </div>

          {writableSources.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No writable source directories configured. Add one in Settings → Sources to import content.
            </p>
          ) : (
            <>
              {writableSources.length > 1 ? (
                <div className="space-y-1.5">
                  <p className="text-xs font-medium text-muted-foreground">Destination</p>
                  <Select value={selected} onValueChange={setDest}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {writableSources.map((s) => (
                        <SelectItem key={s} value={s} className="text-xs">{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Importing into <span className="font-mono">{selected}</span>
                </p>
              )}

              <IngestionPanel destination={{ type: "source", path: selected }} />
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
