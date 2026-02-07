import { useState, useEffect, type Dispatch, type SetStateAction } from "react"

/**
 * useState with automatic localStorage persistence
 *
 * @param key - localStorage key
 * @param initialValue - default value if nothing in localStorage
 * @returns [value, setValue] tuple like useState
 */
export function usePersistedState<T>(
  key: string,
  initialValue: T
): [T, Dispatch<SetStateAction<T>>] {
  // Initialize state from localStorage or use initial value
  const [state, setState] = useState<T>(() => {
    try {
      const item = localStorage.getItem(key)
      if (item !== null) {
        return JSON.parse(item) as T
      }
    } catch (err) {
      console.warn(`Failed to load persisted state for "${key}":`, err)
    }
    return initialValue
  })

  // Save to localStorage whenever state changes
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(state))
    } catch (err) {
      console.warn(`Failed to persist state for "${key}":`, err)
    }
  }, [key, state])

  return [state, setState]
}

/**
 * Helper for persisting a single value (not JSON)
 * Useful for strings, numbers, etc.
 */
export function usePersistedValue<T extends string | number | boolean>(
  key: string,
  initialValue: T
): [T, Dispatch<SetStateAction<T>>] {
  const [state, setState] = useState<T>(() => {
    try {
      const item = localStorage.getItem(key)
      if (item !== null) {
        if (typeof initialValue === "number") return Number(item) as T
        if (typeof initialValue === "boolean") return (item === "true") as T
        return item as T
      }
    } catch (err) {
      console.warn(`Failed to load persisted value for "${key}":`, err)
    }
    return initialValue
  })

  useEffect(() => {
    try {
      localStorage.setItem(key, String(state))
    } catch (err) {
      console.warn(`Failed to persist value for "${key}":`, err)
    }
  }, [key, state])

  return [state, setState]
}
