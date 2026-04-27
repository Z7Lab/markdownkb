import { cn } from "@/lib/utils"
import { useLayout, type Layout } from "@/lib/layout-context"
import { ThemeToggle } from "@/components/theme-toggle"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Monitor, PanelLeft } from "lucide-react"

const LAYOUTS: { value: Layout; label: string; description: string; icon: typeof Monitor }[] = [
  {
    value: "classic",
    label: "Classic",
    description: "Horizontal tab bar across the top",
    icon: Monitor,
  },
  {
    value: "sidebar",
    label: "Sidebar",
    description: "Icon rail on the left, collapsible",
    icon: PanelLeft,
  },
]

export function AppearancePanel() {
  const { layout, setLayout } = useLayout()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">Appearance</h2>
        <p className="text-sm text-muted-foreground">
          Choose your navigation layout and color mode. Saved locally in your browser.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Layout</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-3">
            {LAYOUTS.map(({ value, label, description, icon: Icon }) => (
              <button
                key={value}
                onClick={() => setLayout(value)}
                className={cn(
                  "flex flex-col items-start gap-2 rounded-lg border-2 p-4 text-left transition-colors hover:bg-accent/30",
                  layout === value
                    ? "border-primary bg-accent/20"
                    : "border-border",
                )}
              >
                <Icon className={cn("h-5 w-5", layout === value ? "text-primary" : "text-muted-foreground")} />
                <div>
                  <div className={cn("text-sm font-medium", layout === value && "text-primary")}>{label}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{description}</div>
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Color Mode</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <span className="text-sm text-muted-foreground">Toggle between light and dark mode</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
