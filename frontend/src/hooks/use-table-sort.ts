import { useCallback, useMemo, useState } from "react"

type SortDir = "asc" | "desc"

export function useTableSort<T>(
  data: T[],
  getValue: (item: T, key: string) => string | number | null,
  defaultKey?: string,
) {
  const [sortKey, setSortKey] = useState<string | null>(defaultKey ?? null)
  const [sortDir, setSortDir] = useState<SortDir>("asc")

  const onSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"))
      } else {
        setSortKey(key)
        setSortDir("asc")
      }
    },
    [sortKey],
  )

  const sorted = useMemo(() => {
    if (!sortKey) return data

    return [...data].sort((a, b) => {
      const av = getValue(a, sortKey)
      const bv = getValue(b, sortKey)

      if (av == null && bv == null) return 0
      if (av == null) return 1
      if (bv == null) return -1

      let cmp: number
      if (typeof av === "number" && typeof bv === "number") {
        cmp = av - bv
      } else {
        cmp = String(av).toLowerCase().localeCompare(String(bv).toLowerCase())
      }

      return sortDir === "asc" ? cmp : -cmp
    })
  }, [data, sortKey, sortDir, getValue])

  return { sorted, sortKey, sortDir, onSort }
}
