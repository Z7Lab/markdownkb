import { Layers } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { Scope } from "@/lib/types"

export function ScopePicker({
  scopes,
  value,
  onChange,
}: {
  scopes: Scope[]
  value: string | null
  onChange: (scopeId: string | null) => void
}) {
  return (
    <div className="flex items-center gap-2 px-1">
      <Layers className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
      <Select
        value={value ?? "_all"}
        onValueChange={(v) => onChange(v === "_all" ? null : v)}
      >
        <SelectTrigger className="h-8 text-xs flex-1">
          <SelectValue placeholder="Scope" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="_all">(all sources)</SelectItem>
          {scopes.length === 0 && (
            <SelectItem value="_none" disabled>
              No scopes — create in Settings
            </SelectItem>
          )}
          {scopes.map((s) => (
            <SelectItem key={s.id} value={s.id}>
              {s.name}
              <span className="text-muted-foreground ml-1">
                ({s.folders.length})
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
