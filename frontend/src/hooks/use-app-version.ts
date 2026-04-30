import { useEffect, useState } from "react"
import { api } from "@/lib/api"

interface AppVersion {
  current_version: string
  install_method: "docker" | "native" | "dev"
  update_check_enabled: boolean
}

export function useAppVersion() {
  const [version, setVersion] = useState<AppVersion | null>(null)

  useEffect(() => {
    /* best-effort: version info is non-critical UI chrome */
    api
      .get<AppVersion>("/api/v1/version")
      .then(setVersion)
      .catch(() => {})
  }, [])

  return { version }
}
