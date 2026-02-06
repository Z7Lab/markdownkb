import { createContext, useContext } from "react"

interface NavigationContextValue {
  setActiveTab: (tab: string) => void
}

const NavigationContext = createContext<NavigationContextValue>({
  setActiveTab: () => {},
})

export const NavigationProvider = NavigationContext.Provider
export const useNavigation = () => useContext(NavigationContext)
