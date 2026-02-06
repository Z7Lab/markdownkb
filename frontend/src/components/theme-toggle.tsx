import { Moon, Sun } from "lucide-react"
import { Switch } from "@/components/ui/switch"
import { useEffect, useState } from "react"

function applyTheme(dark: boolean) {
  const root = window.document.documentElement
  root.classList.remove("light", "dark")
  root.classList.add(dark ? "dark" : "light")
  localStorage.setItem("theme", dark ? "dark" : "light")
}

export function ThemeToggle() {
  const [dark, setDark] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem("theme")
    if (stored === "dark" || stored === "light") {
      const d = stored === "dark"
      setDark(d)
      applyTheme(d)
    } else {
      const sys = window.matchMedia("(prefers-color-scheme: dark)").matches
      setDark(sys)
      applyTheme(sys)
    }
  }, [])

  return (
    <div className="flex items-center gap-1.5">
      <Sun className="h-3.5 w-3.5 text-muted-foreground" />
      <Switch
        checked={dark}
        onCheckedChange={(checked) => {
          setDark(checked)
          applyTheme(checked)
        }}
        aria-label="Toggle dark mode"
      />
      <Moon className="h-3.5 w-3.5 text-muted-foreground" />
    </div>
  )
}
