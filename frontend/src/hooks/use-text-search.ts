import { useCallback, useEffect, useRef, useState } from "react"

interface TextSearchState {
  query: string
  matchCount: number
  currentMatch: number
  isOpen: boolean
}

/**
 * Find-in-file text search over a DOM container.
 * Highlights matches using <mark> elements and supports
 * prev/next navigation with distinct styling for the active match.
 */
export function useTextSearch() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<TextSearchState>({
    query: "", matchCount: 0, currentMatch: 0, isOpen: false,
  })
  const marksRef = useRef<HTMLElement[]>([])

  const clearHighlights = useCallback(() => {
    // Remove all <mark> wrappers, restoring original text nodes
    const container = containerRef.current
    if (!container) return
    const marks = container.querySelectorAll("mark[data-text-search]")
    marks.forEach((mark) => {
      const parent = mark.parentNode
      if (parent) {
        parent.replaceChild(document.createTextNode(mark.textContent || ""), mark)
        parent.normalize()
      }
    })
    marksRef.current = []
  }, [])

  const highlightMatches = useCallback((query: string) => {
    clearHighlights()
    const container = containerRef.current
    if (!container || !query) {
      setState((s) => ({ ...s, matchCount: 0, currentMatch: 0 }))
      return
    }

    const lowerQuery = query.toLowerCase()
    const marks: HTMLElement[] = []

    // Walk all text nodes in the container
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
    const textNodes: Text[] = []
    let node: Text | null
    while ((node = walker.nextNode() as Text | null)) {
      textNodes.push(node)
    }

    for (const textNode of textNodes) {
      const text = textNode.textContent || ""
      const lowerText = text.toLowerCase()
      let idx = lowerText.indexOf(lowerQuery)
      if (idx === -1) continue

      // Split text node at match boundaries
      const frag = document.createDocumentFragment()
      let lastIdx = 0
      while (idx !== -1) {
        // Text before match
        if (idx > lastIdx) {
          frag.appendChild(document.createTextNode(text.slice(lastIdx, idx)))
        }
        // Matched text wrapped in <mark>
        const mark = document.createElement("mark")
        mark.setAttribute("data-text-search", "true")
        mark.className = "bg-yellow-200 dark:bg-yellow-800/60 rounded-sm px-0.5"
        mark.textContent = text.slice(idx, idx + query.length)
        frag.appendChild(mark)
        marks.push(mark)

        lastIdx = idx + query.length
        idx = lowerText.indexOf(lowerQuery, lastIdx)
      }
      // Remaining text after last match
      if (lastIdx < text.length) {
        frag.appendChild(document.createTextNode(text.slice(lastIdx)))
      }
      textNode.parentNode?.replaceChild(frag, textNode)
    }

    marksRef.current = marks
    setState((s) => ({
      ...s,
      matchCount: marks.length,
      currentMatch: marks.length > 0 ? 1 : 0,
    }))

    // Scroll to first match
    if (marks.length > 0) {
      marks[0].className = "bg-orange-300 dark:bg-orange-600/80 rounded-sm px-0.5 ring-2 ring-orange-500"
      marks[0].scrollIntoView({ block: "center", behavior: "smooth" })
    }
  }, [clearHighlights])

  const goToMatch = useCallback((index: number) => {
    const marks = marksRef.current
    if (marks.length === 0) return

    // Wrap index
    const idx = ((index - 1) % marks.length + marks.length) % marks.length

    // Reset all marks to default highlight
    marks.forEach((m) => {
      m.className = "bg-yellow-200 dark:bg-yellow-800/60 rounded-sm px-0.5"
    })
    // Highlight current match
    marks[idx].className = "bg-orange-300 dark:bg-orange-600/80 rounded-sm px-0.5 ring-2 ring-orange-500"
    marks[idx].scrollIntoView({ block: "center", behavior: "smooth" })

    setState((s) => ({ ...s, currentMatch: idx + 1 }))
  }, [])

  const setQuery = useCallback((query: string) => {
    setState((s) => ({ ...s, query }))
    highlightMatches(query)
  }, [highlightMatches])

  const nextMatch = useCallback(() => {
    goToMatch(state.currentMatch + 1)
  }, [state.currentMatch, goToMatch])

  const prevMatch = useCallback(() => {
    goToMatch(state.currentMatch - 1)
  }, [state.currentMatch, goToMatch])

  const open = useCallback(() => {
    setState((s) => ({ ...s, isOpen: true }))
  }, [])

  const close = useCallback(() => {
    clearHighlights()
    setState({ query: "", matchCount: 0, currentMatch: 0, isOpen: false })
  }, [clearHighlights])

  // Keyboard shortcut: Ctrl+F / Cmd+F
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "f") {
        e.preventDefault()
        if (state.isOpen) {
          close()
        } else {
          open()
        }
      }
      if (e.key === "Escape" && state.isOpen) {
        close()
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [state.isOpen, open, close])

  return {
    containerRef,
    query: state.query,
    matchCount: state.matchCount,
    currentMatch: state.currentMatch,
    isOpen: state.isOpen,
    setQuery,
    nextMatch,
    prevMatch,
    open,
    close,
  }
}
