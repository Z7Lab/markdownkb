import { useCallback, useEffect, useMemo, useState } from "react"
import { api } from "@/lib/api"
import { toast } from "sonner"

// -- Types matching GET /api/mcp/info and GET /api/mcp/tools ----------------

export type McpFlagKey = "read_only" | "allow_bucket_writes" | "save_document" | "track_history"

export type McpInfo = {
  endpoint: string
  transport: string
  auth_enabled: boolean
  auth_methods: string[]
  flags: Record<string, boolean>
  allowed_hosts: string[]
  allowed_origins: string[]
  rate_limit_per_minute: number
}

export type McpToolParam = {
  name: string
  type: string
  required: boolean
  default: string | null
}

export type McpTool = {
  name: string
  description: string
  write: boolean
  requires_plugin: string | null
  feature_flag: string | null
  enabled: boolean
  disabled_reason: string | null
  parameters: McpToolParam[]
}

export type McpToolsResponse = {
  tools: McpTool[]
  total: number
  enabled: number
  import_errors: { module: string; error: string }[]
}

// -- Flag metadata ----------------------------------------------------------

export const FLAG_DEFS: { key: McpFlagKey; label: string; description: string }[] = [
  {
    key: "read_only",
    label: "Read-only",
    description:
      "Disable all write tools (save_file, delete_file, index_file). Overridden for bucket tools by Allow bucket writes.",
  },
  {
    key: "allow_bucket_writes",
    label: "Allow bucket writes",
    description:
      "Exempt bucket_create/add/push/delete from read-only mode. Buckets are isolated from the main index.",
  },
  {
    key: "save_document",
    label: "Save document tool",
    description: "Enable the save_file MCP tool for writing markdown into configured sources.",
  },
  {
    key: "track_history",
    label: "Track history",
    description: "Record MCP search and chat calls to the web UI history sidebar.",
  },
]

// -- Hook -------------------------------------------------------------------

export interface UseMcpPanelOptions {
  onToggleMcpFlag: (name: string, enabled: boolean) => Promise<void>
}

export function useMcpPanel({ onToggleMcpFlag }: UseMcpPanelOptions) {
  const [info, setInfo] = useState<McpInfo | null>(null)
  const [toolsResp, setToolsResp] = useState<McpToolsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<"ok" | "fail" | null>(null)
  const [newHost, setNewHost] = useState("")
  const [savingHosts, setSavingHosts] = useState(false)
  const [newOrigin, setNewOrigin] = useState("")
  const [savingOrigins, setSavingOrigins] = useState(false)
  const [rateLimit, setRateLimit] = useState<string>("0")
  const [savingRateLimit, setSavingRateLimit] = useState(false)
  const [mcpLogLevel, setMcpLogLevel] = useState("INFO")

  const load = useCallback(async () => {
    try {
      const [infoRes, toolsRes] = await Promise.all([
        api.get<McpInfo>("/api/v1/mcp/info"),
        api.get<McpToolsResponse>("/api/v1/mcp/tools"),
      ])
      setInfo(infoRes)
      setToolsResp(toolsRes)
      setRateLimit(String(infoRes.rate_limit_per_minute ?? 0))
    } catch (err) {
      toast.error(`Failed to load MCP info: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    api.get<{ level: string }>("/api/v1/mcp/log-level")
      .then((r) => setMcpLogLevel(r.level))
      .catch((e) => { console.warn("MCP panel: failed to load log level", e) })
  }, [load])

  const handleMcpLogLevel = useCallback(async (level: string) => {
    try {
      await api.put("/api/v1/mcp/log-level", { level })
      setMcpLogLevel(level)
    } catch (err) {
      toast.error(`Failed to change MCP log level: ${(err as Error).message}`)
    }
  }, [])

  const handleToggleFlag = useCallback(
    async (name: string, enabled: boolean) => {
      await onToggleMcpFlag(name, enabled)
      await load()
    },
    [onToggleMcpFlag, load],
  )

  const handleTestConnection = useCallback(async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await api.get<McpToolsResponse>("/api/v1/mcp/tools")
      setTestResult("ok")
      toast.success(`MCP ready — ${res.enabled} of ${res.total} tools active`)
    } catch (err) {
      setTestResult("fail")
      toast.error(`MCP unreachable: ${(err as Error).message}`)
    } finally {
      setTesting(false)
    }
  }, [])

  const handleAddHost = useCallback(async () => {
    if (!info || !newHost.trim()) return
    const next = [...info.allowed_hosts, newHost.trim()]
    setSavingHosts(true)
    try {
      await api.put("/api/v1/mcp/allowed-hosts", { allowed_hosts: next })
      setNewHost("")
      await load()
      toast.success("Allowed hosts updated. Restart MCP server to apply.")
    } catch (err) {
      toast.error(`Failed to save: ${(err as Error).message}`)
    } finally {
      setSavingHosts(false)
    }
  }, [info, newHost, load])

  const handleRemoveHost = useCallback(
    async (host: string) => {
      if (!info) return
      const next = info.allowed_hosts.filter((h) => h !== host)
      setSavingHosts(true)
      try {
        await api.put("/api/v1/mcp/allowed-hosts", { allowed_hosts: next })
        await load()
      } catch (err) {
        toast.error(`Failed to save: ${(err as Error).message}`)
      } finally {
        setSavingHosts(false)
      }
    },
    [info, load],
  )

  const handleAddOrigin = useCallback(async () => {
    if (!info || !newOrigin.trim()) return
    const next = [...info.allowed_origins, newOrigin.trim()]
    setSavingOrigins(true)
    try {
      await api.put("/api/v1/mcp/allowed-origins", { allowed_origins: next })
      setNewOrigin("")
      await load()
      toast.success("Allowed origins updated. Restart MCP server to apply.")
    } catch (err) {
      toast.error(`Failed to save: ${(err as Error).message}`)
    } finally {
      setSavingOrigins(false)
    }
  }, [info, newOrigin, load])

  const handleRemoveOrigin = useCallback(
    async (origin: string) => {
      if (!info) return
      const next = info.allowed_origins.filter((o) => o !== origin)
      setSavingOrigins(true)
      try {
        await api.put("/api/v1/mcp/allowed-origins", { allowed_origins: next })
        await load()
      } catch (err) {
        toast.error(`Failed to save: ${(err as Error).message}`)
      } finally {
        setSavingOrigins(false)
      }
    },
    [info, load],
  )

  const handleSaveRateLimit = useCallback(async () => {
    const parsed = parseInt(rateLimit, 10)
    if (isNaN(parsed) || parsed < 0) {
      toast.error("Rate limit must be 0 or a positive integer")
      return
    }
    setSavingRateLimit(true)
    try {
      await api.put("/api/v1/mcp/rate-limit", { per_minute: parsed })
      await load()
      toast.success(
        parsed === 0
          ? "Rate limit disabled. Restart MCP server to apply."
          : `Rate limit set to ${parsed}/min. Restart MCP server to apply.`,
      )
    } catch (err) {
      toast.error(`Failed to save: ${(err as Error).message}`)
    } finally {
      setSavingRateLimit(false)
    }
  }, [rateLimit, load])

  const toolsByCategory = useMemo(() => {
    if (!toolsResp) return { enabled: [], disabled: [] }
    return {
      enabled: toolsResp.tools.filter((t) => t.enabled),
      disabled: toolsResp.tools.filter((t) => !t.enabled),
    }
  }, [toolsResp])

  return {
    info,
    toolsResp,
    loading,
    testing,
    testResult,
    newHost,
    setNewHost,
    savingHosts,
    newOrigin,
    setNewOrigin,
    savingOrigins,
    rateLimit,
    setRateLimit,
    savingRateLimit,
    mcpLogLevel,
    toolsByCategory,
    handleMcpLogLevel,
    handleToggleFlag,
    handleTestConnection,
    handleAddHost,
    handleRemoveHost,
    handleAddOrigin,
    handleRemoveOrigin,
    handleSaveRateLimit,
  }
}
