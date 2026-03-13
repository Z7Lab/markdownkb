export interface PluginEndpoint {
  method: string
  path: string
  description: string
}

export interface ConfigFieldSchema {
  type: string
  default: unknown
  label?: string
  description?: string
  min?: number
  max?: number
}

export interface PluginInfo {
  name: string
  display_name: string
  description: string
  version: string
  author: string
  icon: string
  category: string
  feature_flag: string
  enabled: boolean
  source: string
  error: string | null
  endpoints: PluginEndpoint[]
  config_schema: Record<string, ConfigFieldSchema>
  config: Record<string, unknown>
  requires: string[]
  has_manifest: boolean
}

export interface CoreFeature {
  name: string
  display_name: string
  description: string
  icon: string
  category: string
  section: "core" | "mcp"
  enabled: boolean
}
