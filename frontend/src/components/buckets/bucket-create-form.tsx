import { useState } from "react"
import { type useBuckets } from "@/hooks/use-buckets"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Clock, Infinity as InfinityIcon } from "lucide-react"
import { BucketPathStatus } from "./bucket-path-status"

// Color palette — must match _BUCKET_COLORS in backend router.py
const BUCKET_PALETTE = [
  "#6366f1", "#8b5cf6", "#ec4899", "#f97316",
  "#14b8a6", "#06b6d4", "#84cc16", "#f59e0b",
]

export interface BucketCreateFormProps {
  onCreated: (id: string) => void
  onCancel: () => void
  createBucket: ReturnType<typeof useBuckets>["createBucket"]
}

export function BucketCreateForm({
  onCreated,
  onCancel,
  createBucket,
}: BucketCreateFormProps) {
  const [name, setName] = useState("")
  const [path, setPath] = useState("")
  const [glob, setGlob] = useState("**/*.md")
  const [expiresIn, setExpiresIn] = useState<number | null>(null)
  const [color, setColor] = useState<string | null>(null)

  async function handleCreate() {
    if (!name.trim() || !path.trim()) return
    const res = await createBucket({
      name: name.trim(),
      sources: [{ path: path.trim(), glob: glob.trim() || "**/*.md" }],
      expires_in: expiresIn,
      color: color ?? undefined,
    })
    if (res) {
      onCreated(res.id)
    }
  }

  return (
    <div className="p-6 max-w-xl">
      <h2 className="text-base font-semibold mb-4">New Bucket</h2>
      <div className="space-y-4">
        <div>
          <label htmlFor="bucket-create-name" className="text-sm font-medium">Name</label>
          <Input
            id="bucket-create-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. grpc-evaluation"
            className="mt-1"
            autoFocus
          />
        </div>
        <div>
          <label htmlFor="bucket-create-path" className="text-sm font-medium">Source path</label>
          <Input
            id="bucket-create-path"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="Absolute path to file or directory"
            className="mt-1"
          />
          <BucketPathStatus path={path} />
        </div>
        <div>
          <label htmlFor="bucket-create-glob" className="text-sm font-medium">Glob pattern</label>
          <Input
            id="bucket-create-glob"
            value={glob}
            onChange={(e) => setGlob(e.target.value)}
            placeholder="**/*.md"
            className="mt-1"
          />
        </div>
        <div>
          <span id="bucket-create-expires-label" className="text-sm font-medium">Expires in</span>
          <Select
            value={expiresIn === null ? "permanent" : String(expiresIn)}
            onValueChange={(v) => {
              if (v === "permanent") setExpiresIn(null)
              else setExpiresIn(Number(v))
            }}
          >
            <SelectTrigger className="mt-1" aria-labelledby="bucket-create-expires-label">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="permanent">
                <span className="flex items-center gap-1.5"><InfinityIcon className="h-4 w-4" /> Permanent</span>
              </SelectItem>
              <SelectItem value="3600">
                <span className="flex items-center gap-1.5"><Clock className="h-4 w-4" /> 1 hour</span>
              </SelectItem>
              <SelectItem value="86400">
                <span className="flex items-center gap-1.5"><Clock className="h-4 w-4" /> 24 hours</span>
              </SelectItem>
              <SelectItem value="604800">
                <span className="flex items-center gap-1.5"><Clock className="h-4 w-4" /> 7 days</span>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <span id="bucket-create-color-label" className="text-sm font-medium">Color</span>
          <div className="flex items-center gap-2 mt-1" role="group" aria-labelledby="bucket-create-color-label">
            {BUCKET_PALETTE.map((c) => (
              <button
                key={c}
                type="button"
                title={c}
                className="h-6 w-6 rounded-full border-2 transition-transform hover:scale-110"
                style={{
                  backgroundColor: c,
                  borderColor: color === c ? "hsl(var(--foreground))" : "transparent",
                }}
                onClick={() => setColor(color === c ? null : c)}
              />
            ))}
            <span className="text-xs text-muted-foreground ml-1">
              {color ? color : "auto-assigned"}
            </span>
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <Button
            size="sm"
            onClick={handleCreate}
            disabled={!name.trim() || !path.trim()}
          >
            Create
          </Button>
          <Button size="sm" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  )
}
