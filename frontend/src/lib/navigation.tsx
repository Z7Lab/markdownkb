import type { ReactNode } from "react"
import { NavigationContext, type NavigationContextValue } from "@/contexts/navigation"

// Export provider component
export function NavigationProvider({ value, children }: { value: NavigationContextValue; children: ReactNode }) {
  return <NavigationContext.Provider value={value}>{children}</NavigationContext.Provider>
}
