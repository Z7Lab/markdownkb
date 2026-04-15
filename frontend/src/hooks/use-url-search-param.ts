import { useLocation } from "wouter"
import { useCallback, useMemo } from "react"

/**
 * Hook for managing URL search parameters.
 * Allows reading and setting individual query params without losing others.
 * Works with wouter's location string format (/path?query=value).
 */
export function useUrlSearchParam(paramName: string) {
  const [location, setLocation] = useLocation()

  // Parse search params from location string
  const searchParams = useMemo(() => {
    const searchIndex = location.indexOf("?")
    const searchStr = searchIndex > -1 ? location.slice(searchIndex + 1) : ""
    return new URLSearchParams(searchStr)
  }, [location])

  const getValue = useCallback(() => {
    return searchParams.get(paramName)
  }, [searchParams, paramName])

  const setValue = useCallback(
    (value: string | null) => {
      const pathIndex = location.indexOf("?")
      const pathname = pathIndex > -1 ? location.slice(0, pathIndex) : location

      const newParams = new URLSearchParams(searchParams.toString())
      if (value) {
        newParams.set(paramName, value)
      } else {
        newParams.delete(paramName)
      }

      const newSearch = newParams.toString()
      const newLocation = newSearch ? `${pathname}?${newSearch}` : pathname
      setLocation(newLocation, { replace: true })
    },
    [location, paramName, searchParams, setLocation]
  )

  return [getValue(), setValue] as const
}
