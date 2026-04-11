import { useEffect, useState } from "react"
import { api } from "@/lib/api"

interface PathCheckResult {
  accessible: boolean
  in_docker: boolean
  already_configured?: boolean
}

type PathCheckState =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "ok" }
  | { status: "not_found" }
  | { status: "needs_restart" }
  | { status: "bad_mount" }

export function usePathCheck(path: string, debounceMs = 400): PathCheckState {
  const [state, setState] = useState<PathCheckState>({ status: "idle" })

  useEffect(() => {
    const trimmed = path.trim()
    if (!trimmed) {
      setState({ status: "idle" })
      return
    }

    setState({ status: "checking" })

    const timer = setTimeout(async () => {
      try {
        const result = await api.get<PathCheckResult>(
          `/api/check-path?path=${encodeURIComponent(trimmed)}`
        )
        if (result.accessible) {
          setState({ status: "ok" })
        } else if (result.in_docker) {
          setState({ status: result.already_configured ? "bad_mount" : "needs_restart" })
        } else {
          setState({ status: "not_found" })
        }
      } catch {
        setState({ status: "idle" })
      }
    }, debounceMs)

    return () => clearTimeout(timer)
  }, [path, debounceMs])

  return state
}
