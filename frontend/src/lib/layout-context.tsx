import { createContext, useContext, useState } from "react"
import type { ReactNode } from "react"

export type Layout = "classic" | "sidebar"

interface LayoutContextValue {
  layout: Layout
  setLayout: (layout: Layout) => void
}

const LayoutContext = createContext<LayoutContextValue>({
  layout: "classic",
  setLayout: () => {},
})

export function LayoutProvider({ children }: { children: ReactNode }) {
  const [layout, setLayoutState] = useState<Layout>(() => {
    const stored = localStorage.getItem("mdkb-layout")
    return stored === "classic" ? "classic" : "sidebar"
  })

  const setLayout = (l: Layout) => {
    setLayoutState(l)
    localStorage.setItem("mdkb-layout", l)
  }

  return (
    <LayoutContext.Provider value={{ layout, setLayout }}>
      {children}
    </LayoutContext.Provider>
  )
}

export function useLayout() {
  return useContext(LayoutContext)
}
