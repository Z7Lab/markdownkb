import { useState } from "react"
import { type Bucket, type useBuckets } from "@/hooks/use-buckets"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Clock, Infinity as InfinityIcon, X, Check } from "lucide-react"

// Color palette — must match _BUCKET_COLORS in backend router.py
const BUCKET_PALETTE = [
  "#6366f1", "#8b5cf6", "#ec4899", "#f97316",
  "#14b8a6", "#06b6d4", "#84cc16", "#f59e0b",
]

export interface BucketEditFormProps {
  bucket: Bucket
  onSave: () => void
  onCancel: () => void
  updateBucket: ReturnType<typeof useBuckets>["updateBucket"]
}

export function BucketEditForm({
  bucket,
  onSave,
  onCancel,
  updateBucket,
}: BucketEditFormProps) {
  const [name, setName] = useState(bucket.name)
  const [color, setColor] = useState<string | null>(bucket.color)
  const [expiresIn, setExpiresIn] = useState<number | null | "keep">("keep")

  async function handleSave() {
    const params: Parameters<typeof updateBucket>[1] = {}
    if (name.trim() && name.trim() !== bucket.name) params.name = name.trim()
    if (color !== bucket.color) params.color = color
    if (expiresIn !== "keep") params.expires_in = expiresIn
    if (Object.keys(params).length > 0) {
      await updateBucket(bucket.id, params)
    }
    onSave()
  }

  return (
    <Card className="mb-4">
      <CardContent className="pt-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Edit bucket</span>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onCancel}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
        <div>
          <label htmlFor="bucket-edit-name" className="text-xs font-medium">Name</label>
          <Input
            id="bucket-edit-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 h-8 text-sm"
            autoFocus
          />
        </div>
        <div>
          <span id="bucket-edit-expires-label" className="text-xs font-medium">Expiration</span>
          <Select
            value={expiresIn === "keep" ? "keep" : expiresIn === null ? "permanent" : String(expiresIn)}
            onValueChange={(v) => {
              if (v === "keep") setExpiresIn("keep")
              else if (v === "permanent") setExpiresIn(null)
              else setExpiresIn(Number(v))
            }}
          >
            <SelectTrigger className="mt-1 h-8 text-sm" aria-labelledby="bucket-edit-expires-label">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="keep">
                <span className="text-muted-foreground">
                  {bucket.expires_at
                    ? `Keep: expires ${new Date(bucket.expires_at + "Z").toLocaleDateString()}`
                    : "Keep: permanent"}
                </span>
              </SelectItem>
              <SelectItem value="permanent">
                <span className="flex items-center gap-1.5"><InfinityIcon className="h-3.5 w-3.5" /> Make permanent</span>
              </SelectItem>
              <SelectItem value="3600">
                <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> 1 hour from now</span>
              </SelectItem>
              <SelectItem value="86400">
                <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> 24 hours from now</span>
              </SelectItem>
              <SelectItem value="604800">
                <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> 7 days from now</span>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <span id="bucket-edit-color-label" className="text-xs font-medium">Color</span>
          <div className="flex items-center gap-1.5 mt-1" role="group" aria-labelledby="bucket-edit-color-label">
            {BUCKET_PALETTE.map((c) => (
              <button
                key={c}
                type="button"
                title={c}
                className="h-5 w-5 rounded-full border-2 transition-transform hover:scale-110"
                style={{
                  backgroundColor: c,
                  borderColor: (color ?? bucket.color) === c ? "hsl(var(--foreground))" : "transparent",
                }}
                onClick={() => setColor(color === c ? bucket.color : c)}
              />
            ))}
          </div>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={handleSave} className="gap-1">
            <Check className="h-3.5 w-3.5" /> Save
          </Button>
          <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
        </div>
      </CardContent>
    </Card>
  )
}
