import { useLocation, useSearch } from "wouter"
import { useCallback, useMemo } from "react"

/**
 * Hook for managing URL search parameters.
 * Uses wouter's useSearch() for reading (returns location.search, not pathname)
 * and useLocation() navigate for writing.
 */
export function useUrlSearchParam(paramName: string) {
  const [location, setLocation] = useLocation()
  const search = useSearch()

  const searchParams = useMemo(() => new URLSearchParams(search), [search])

  const setValue = useCallback(
    (value: string | null) => {
      const newParams = new URLSearchParams(searchParams.toString())
      if (value) {
        newParams.set(paramName, value)
      } else {
        newParams.delete(paramName)
      }
      const newSearch = newParams.toString()
      const newLocation = newSearch ? `${location}?${newSearch}` : location
      setLocation(newLocation, { replace: true })
    },
    [location, paramName, searchParams, setLocation]
  )

  return [searchParams.get(paramName), setValue] as const
}
