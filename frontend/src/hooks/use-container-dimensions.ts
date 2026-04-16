import { useEffect, useRef, useState } from "react"

interface Dimensions {
  width: number
  height: number
}

/** Track an element's content-rect dimensions via ResizeObserver */
export function useContainerDimensions(): {
  containerRef: React.RefObject<HTMLDivElement | null>
  dimensions: Dimensions
} {
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState<Dimensions>({ width: 800, height: 600 })

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0]!.contentRect
      setDimensions({ width: Math.floor(width), height: Math.floor(height) })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return { containerRef, dimensions }
}
