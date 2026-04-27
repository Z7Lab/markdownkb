import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { FileViewerDialog } from "@/components/ui/file-viewer-dialog"

export interface DocsOverTimePoint {
  date: string
  count: number
}

export interface DocsBySourceItem {
  source: string
  label: string
  count: number
}

export interface RichestFileItem {
  path: string
  filename: string
  chunks: number
}

export interface DashboardChartsData {
  docs_over_time: DocsOverTimePoint[]
  docs_by_source: DocsBySourceItem[]
  richest_files: RichestFileItem[]
}

// ── Palette: cycles through CSS vars so it respects light/dark ───────────────
const SLICE_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
]

function sliceColor(i: number) {
  return SLICE_COLORS[i % SLICE_COLORS.length]
}


// ── 1. Area / bar timeline chart ──────────────────────────────────────────────
export function DocsOverTimeChart({ data }: { data: DocsOverTimePoint[] }) {
  const [tip, setTip] = useState<{ x: number; y: number; label: string; value: number } | null>(null)

  const max = Math.max(...data.map((d) => d.count), 1)
  const W = 560
  const H = 120
  const padL = 0
  const padR = 0
  const padT = 8
  const padB = 28
  const innerW = W - padL - padR
  const innerH = H - padT - padB
  const n = data.length

  const barW = Math.floor(innerW / n) - 2

  const formatDate = (iso: string) => {
    const d = new Date(iso + "T00:00:00")
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
  }

  const hasAny = data.some((d) => d.count > 0)

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Indexing Activity — Last 14 Days</CardTitle>
      </CardHeader>
      <CardContent>
        {!hasAny ? (
          <div className="flex items-center justify-center h-[148px] text-sm text-muted-foreground">
            No indexing activity yet
          </div>
        ) : (
          <div className="relative select-none">
            <svg
              viewBox={`0 0 ${W} ${H}`}
              className="w-full"
              style={{ height: H }}
              onMouseLeave={() => setTip(null)}
            >
              <defs>
                <linearGradient id="bar-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.85" />
                  <stop offset="100%" stopColor="var(--primary)" stopOpacity="0.3" />
                </linearGradient>
              </defs>

              {/* Horizontal grid lines */}
              {[0.25, 0.5, 0.75, 1].map((frac) => {
                const y = padT + innerH * (1 - frac)
                return (
                  <line
                    key={frac}
                    x1={padL}
                    y1={y}
                    x2={W - padR}
                    y2={y}
                    stroke="hsl(var(--border))"
                    strokeWidth={0.5}
                  />
                )
              })}

              {/* Bars */}
              {data.map((d, i) => {
                const barH = d.count === 0 ? 0 : Math.max(2, (d.count / max) * innerH)
                const x = padL + (i / n) * innerW + 1
                const y = padT + innerH - barH
                return (
                  <rect
                    key={d.date}
                    x={x}
                    y={y}
                    width={barW}
                    height={barH}
                    rx={2}
                    fill="url(#bar-grad)"
                    className="cursor-pointer"
                    onMouseEnter={(e) => {
                      const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement)
                        .getBoundingClientRect()
                      setTip({
                        x: e.clientX - rect.left,
                        y: e.clientY - rect.top - 36,
                        label: formatDate(d.date),
                        value: d.count,
                      })
                    }}
                  />
                )
              })}

              {/* X-axis labels — show every other one to avoid crowding */}
              {data.map((d, i) => {
                if (i % 2 !== 0) return null
                const x = padL + (i / n) * innerW + barW / 2
                const parts = d.date.split("-")
                const label = `${parts[1]}/${parts[2]}`
                return (
                  <text
                    key={d.date}
                    x={x}
                    y={H - 6}
                    textAnchor="middle"
                    fontSize={9}
                    fill="var(--muted-foreground)"
                  >
                    {label}
                  </text>
                )
              })}
            </svg>

            {tip && (
              <div
                className="pointer-events-none absolute z-50 rounded-md border bg-popover px-2.5 py-1.5 text-xs shadow-md"
                style={{ left: tip.x, top: tip.y, transform: "translateX(-50%)" }}
              >
                <span className="text-muted-foreground">{tip.label}: </span>
                <span className="font-semibold text-foreground">{tip.value} docs</span>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ── 2. Donut chart ────────────────────────────────────────────────────────────
export function DocsBySourceChart({ data }: { data: DocsBySourceItem[] }) {
  const [hovered, setHovered] = useState<number | null>(null)

  const total = data.reduce((s, d) => s + d.count, 0)
  if (total === 0 || data.length <= 1) return null

  const R = 52
  const CX = 72
  const CY = 72
  const stroke = 24

  let cumAngle = -Math.PI / 2

  const slices = data.map((d, i) => {
    const frac = d.count / total
    const angle = frac * 2 * Math.PI
    const start = cumAngle
    cumAngle += angle
    const end = cumAngle

    const x1 = CX + R * Math.cos(start)
    const y1 = CY + R * Math.sin(start)
    const x2 = CX + R * Math.cos(end)
    const y2 = CY + R * Math.sin(end)
    const large = angle > Math.PI ? 1 : 0

    return { d: d, i, x1, y1, x2, y2, large, frac, color: sliceColor(i) }
  })

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Docs by Source</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4">
          <svg viewBox="0 0 144 144" className="shrink-0" style={{ width: 120, height: 120 }}>
            {slices.map(({ d, i, x1, y1, x2, y2, large, color, frac }) => {
              const isHovered = hovered === i
              const angle = frac * 2 * Math.PI
              const pathD = angle >= 2 * Math.PI - 0.001
                ? `M ${CX} ${CY - R} A ${R} ${R} 0 1 1 ${CX - 0.001} ${CY - R} Z`
                : `M ${x1} ${y1} A ${R} ${R} 0 ${large} 1 ${x2} ${y2}`

              return (
                <path
                  key={d.source}
                  d={pathD}
                  fill="none"
                  stroke={color}
                  strokeWidth={isHovered ? stroke + 4 : stroke}
                  strokeLinecap="butt"
                  className="transition-all duration-150 cursor-pointer"
                  onMouseEnter={() => setHovered(i)}
                  onMouseLeave={() => setHovered(null)}
                >
                  <title>{d.label}: {d.count} docs ({Math.round(frac * 100)}%)</title>
                </path>
              )
            })}
            {/* Center label */}
            <text x={CX} y={CY - 6} textAnchor="middle" fontSize={14} fontWeight="600" fill="var(--foreground)">
              {total}
            </text>
            <text x={CX} y={CY + 10} textAnchor="middle" fontSize={8} fill="var(--muted-foreground)">
              total docs
            </text>
          </svg>

          {/* Legend */}
          <div className="flex flex-col gap-1.5 min-w-0 flex-1">
            {slices.map(({ d, i, color, frac }) => (
              <div
                key={d.source}
                className="flex items-center gap-2 text-xs cursor-default"
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
              >
                <div className="shrink-0 h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
                <span className="truncate text-muted-foreground flex-1" title={d.source}>{d.label}</span>
                <span className="shrink-0 font-medium tabular-nums">{d.count}</span>
                <span className="shrink-0 text-muted-foreground tabular-nums">
                  {Math.round(frac * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ── 3. Horizontal bar — richest files ─────────────────────────────────────────
export function RichestFilesChart({
  data,
  onSelectFile,
}: {
  data: RichestFileItem[]
  onSelectFile: (path: string) => void
}) {
  if (data.length === 0) return null

  const max = Math.max(...data.map((d) => d.chunks))

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Most Content-Dense Files</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {data.map((d, i) => (
            <button
              key={d.path}
              className="w-full text-left group"
              onClick={() => onSelectFile(d.path)}
              title={d.path}
            >
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-xs text-muted-foreground truncate flex-1 group-hover:text-foreground transition-colors">
                  {d.filename}
                </span>
                <span className="text-xs font-medium tabular-nums shrink-0">{d.chunks} chunks</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{
                    width: `${(d.chunks / max) * 100}%`,
                    background: sliceColor(i),
                  }}
                />
              </div>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// ── Composed export: all three charts with file viewer wired up ───────────────
export function DashboardCharts({ data }: { data: DashboardChartsData }) {
  const [viewingFile, setViewingFile] = useState<string | null>(null)

  return (
    <>
      <DocsOverTimeChart data={data.docs_over_time} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <DocsBySourceChart data={data.docs_by_source} />
        <RichestFilesChart data={data.richest_files} onSelectFile={setViewingFile} />
      </div>

      <FileViewerDialog path={viewingFile} onClose={() => setViewingFile(null)} />
    </>
  )
}
