import { useEffect, useState } from "react"
import { api } from "@/lib/api"

/**
 * Probe the wiki_compile plugin once at mount. Returns true if the
 * /targets endpoint responds successfully (plugin enabled), false
 * otherwise. Used to conditionally show the "Compile to wiki" button
 * only when the plugin is available.
 *
 * Intentionally shared state via module-level cache — every component
 * that asks should get the same answer, and a single probe per page
 * load is enough.
 */
let cached: boolean | null = null
let inflight: Promise<boolean> | null = null

async function probe(): Promise<boolean> {
  if (cached !== null) return cached
  if (inflight) return inflight
  inflight = api.get<{ wikis: unknown[] }>("/api/v1/wiki-compile/wikis")
    .then(() => { cached = true; return true })
    .catch(() => { cached = false; return false })
    .finally(() => { inflight = null })
  return inflight
}

export function useWikiCompileAvailable(): boolean {
  const [available, setAvailable] = useState<boolean>(cached ?? false)
  useEffect(() => {
    let cancelled = false
    probe().then((v) => { if (!cancelled) setAvailable(v) })
    return () => { cancelled = true }
  }, [])
  return available
}
