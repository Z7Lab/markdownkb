import { createContext } from "react"

export interface NavigationContextValue {
  setActiveTab: (tab: string) => void
}

export const NavigationContext = createContext<NavigationContextValue>({
  setActiveTab: () => {},
})
