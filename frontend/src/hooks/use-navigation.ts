import { useContext } from "react"
import { NavigationContext } from "@/contexts/navigation"

export function useNavigation() {
  return useContext(NavigationContext)
}
