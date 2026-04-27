import { Moon, Sun } from "lucide-react"
import { Switch } from "@/components/ui/switch"
import { useState } from "react"

function applyTheme(dark: boolean) {
  const root = window.document.documentElement
  root.classList.remove("light", "dark")
  root.classList.add(dark ? "dark" : "light")
  localStorage.setItem("theme", dark ? "dark" : "light")
}

export function ThemeToggle({ compact }: { compact?: boolean } = {}) {
  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem("theme")
    if (stored === "dark" || stored === "light") {
      const d = stored === "dark"
      applyTheme(d)
      return d
    } else {
      const sys = window.matchMedia("(prefers-color-scheme: dark)").matches
      applyTheme(sys)
      return sys
    }
  })

  const toggle = () => {
    setDark((d) => {
      applyTheme(!d)
      return !d
    })
  }

  if (compact) {
    return (
      <button
        onClick={toggle}
        aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
        className="flex items-center justify-center h-7 w-7 rounded-md text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors"
      >
        {dark ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
      </button>
    )
  }

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
